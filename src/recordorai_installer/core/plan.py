"""Plan builder — turn user choices into an ordered list of install steps.

A :class:`Plan` is just a list of :class:`Step` instances. Each step is
small, idempotent, and reversible (the executor can roll back failed
steps via the step's ``undo`` callback).

The plan is fully serializable so the wizard can show a "review what
will happen" screen before pressing Install.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .detect import Environment

# ──────────────────────────────────────────────────────────────────────────
# User choices (what the wizard collects)
# ──────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Choices:
    """Everything the wizard collects from the user.

    The TUI and Tauri front-ends both produce a Choices instance and
    hand it to :func:`build_plan`.
    """

    runtime: str  # one of: standalone | openclaw | pi-mono | alice-runtime | hermes
    palace_root: str  # absolute path; default ~/.recordorai
    edition: str = "community"  # community | pro
    license_key: str | None = None  # required iff edition == "pro"

    # Feature toggles — drive which optional dependency groups install.
    enable_audio: bool = False  # Phase 6 — WhisperX
    enable_image: bool = False  # Phase 6 — Qwen3-VL
    enable_video: bool = False  # Phase 6 — ffmpeg + audio + image deps
    enable_documents: bool = True  # Phase 6.5 — PDF + Office + HTML (small deps)
    enable_rerank_ane: bool = True  # CoreML/ANE rerank (Apple Silicon only)

    # Pro-only toggles (gated by license validation in license.py).
    enable_multi_tenant: bool = False
    enable_sync: bool = False
    enable_smart_observer: bool = False


# ──────────────────────────────────────────────────────────────────────────
# Step primitive
# ──────────────────────────────────────────────────────────────────────────


@dataclass
class Step:
    """One install action.

    Steps are pure data on construction — the actual side effect runs
    when :func:`recordorai_installer.core.exec.execute` calls
    ``step.do()``. The optional ``undo`` is invoked by the executor if
    a later step fails.

    The :attr:`kind` field categorizes the step so the wizard can show
    progress per phase ("Installing Python deps...", "Configuring
    OpenClaw...", etc.).
    """

    kind: str  # "deps" | "fs" | "config" | "register" | "verify" | "license"
    title: str  # one-line human label, shown in progress UI
    detail: str = ""  # multi-line detail (logged but not always shown)
    do: Callable[[], None] | None = None
    undo: Callable[[], None] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Plan:
    """Ordered list of steps + computed summary."""

    steps: list[Step] = field(default_factory=list)
    summary: str = ""

    def __len__(self) -> int:
        return len(self.steps)

    def is_empty(self) -> bool:
        return not self.steps

    def kinds(self) -> list[str]:
        """Distinct step kinds, in order of first appearance."""
        seen: list[str] = []
        for s in self.steps:
            if s.kind not in seen:
                seen.append(s.kind)
        return seen

    def by_kind(self, kind: str) -> list[Step]:
        return [s for s in self.steps if s.kind == kind]


# ──────────────────────────────────────────────────────────────────────────
# Builder
# ──────────────────────────────────────────────────────────────────────────


def build_plan(env: Environment, choices: Choices) -> Plan:
    """Construct a :class:`Plan` from detected environment + user choices.

    The builder defers to per-runtime adapters for the runtime-specific
    steps. Adapters live in :mod:`recordorai_installer.adapters`.
    """
    # Local import to avoid a circular dep at module-load time.
    from ..adapters import get_adapter

    plan = Plan()

    # 1) Validate the environment fits.
    plan.steps.extend(_preflight_steps(env, choices))

    # 2) Install RecordorAI Python deps (sized by feature toggles).
    plan.steps.extend(_dep_steps(env, choices))

    # 3) Filesystem layout — palace root, log dir, cache dir.
    plan.steps.extend(_filesystem_steps(env, choices))

    # 4) Runtime adapter steps — registers RecordorAI with the chosen runtime.
    adapter = get_adapter(choices.runtime)
    plan.steps.extend(adapter.plan_steps(env, choices))

    # 5) License activation (Pro only). Community skips this.
    if choices.edition == "pro":
        plan.steps.extend(_license_steps(env, choices))

    # 6) Verification — sanity-check the install before declaring success.
    plan.steps.extend(_verify_steps(env, choices, adapter))

    plan.summary = _summary(env, choices, plan)
    return plan


# ──────────────────────────────────────────────────────────────────────────
# Step builders (pure-data — actual side effects bound at exec time)
# ──────────────────────────────────────────────────────────────────────────


def _preflight_steps(env: Environment, choices: Choices) -> list[Step]:
    """Cheap, fail-fast checks that surface problems before we touch
    anything (wrong Python version, missing system binary, etc.)."""
    steps: list[Step] = []

    py_ok = env.python.version >= (3, 9)
    steps.append(
        Step(
            kind="verify",
            title="Check Python ≥ 3.9",
            detail=(
                f"Detected Python {'.'.join(str(x) for x in env.python.version)}; "
                f"RecordorAI requires 3.9 or higher."
            ),
            metadata={"check": "python_version", "passes": py_ok},
        )
    )

    if choices.enable_video:
        # Phase 6 video ingest needs ffmpeg as a system binary.
        import shutil

        ffmpeg_present = shutil.which("ffmpeg") is not None
        steps.append(
            Step(
                kind="verify",
                title="Check ffmpeg available",
                detail=(
                    "Video ingest requires ffmpeg on PATH. "
                    "macOS: `brew install ffmpeg`. Linux: `apt install ffmpeg`. "
                    "Windows: install from gyan.dev/ffmpeg."
                ),
                metadata={"check": "ffmpeg", "passes": ffmpeg_present},
            )
        )

    return steps


def _dep_steps(env: Environment, choices: Choices) -> list[Step]:
    """Pip install RecordorAI core + the opt-in extras the user selected."""
    extras: list[str] = []
    if choices.enable_documents:
        extras.append("document-all")
    if choices.enable_audio:
        extras.append("multimodal-audio")
    if choices.enable_image:
        extras.append("multimodal-image")
    if choices.enable_video:
        extras.append("multimodal-video")
    if choices.enable_rerank_ane and env.host.is_apple_silicon:
        extras.append("multimodal-rerank")

    extras_suffix = f"[{','.join(extras)}]" if extras else ""
    pkg_spec = f"recordorai{extras_suffix}"

    steps = [
        Step(
            kind="deps",
            title="Install RecordorAI core",
            detail=f"pip install '{pkg_spec}'",
            metadata={"package": pkg_spec, "extras": extras},
        )
    ]

    return steps


def _filesystem_steps(env: Environment, choices: Choices) -> list[Step]:
    """Create the palace root + ensure cache/log dirs exist."""
    steps = [
        Step(
            kind="fs",
            title=f"Create palace root at {choices.palace_root}",
            detail=(
                "RecordorAI stores all your data here. The directory is "
                "created with user-only permissions."
            ),
            metadata={"path": choices.palace_root},
        ),
    ]
    return steps


def _license_steps(env: Environment, choices: Choices) -> list[Step]:
    """Validate the user's Pro subscription is active."""
    return [
        Step(
            kind="license",
            title="Validate Pro license",
            detail=(
                "Confirms your monthly subscription is active. "
                "RecordorAI runs offline once activated, with a 7-day "
                "grace period if the license server is unreachable."
            ),
            metadata={"license_key": choices.license_key, "edition": "pro"},
        )
    ]


def _verify_steps(env: Environment, choices: Choices, adapter) -> list[Step]:
    """Final post-install sanity checks."""
    return [
        Step(
            kind="verify",
            title="Verify RecordorAI is importable",
            detail="`python -c 'import recordorai; recordorai.__version__'` must succeed.",
            metadata={"check": "import"},
        ),
        Step(
            kind="verify",
            title=f"Verify {choices.runtime} integration",
            detail=adapter.verify_description(),
            metadata={"check": "runtime_integration", "runtime": choices.runtime},
        ),
    ]


def _summary(env: Environment, choices: Choices, plan: Plan) -> str:
    """Human-readable one-paragraph summary the wizard shows on the
    review screen."""
    extras = []
    if choices.enable_documents:
        extras.append("documents")
    if choices.enable_audio:
        extras.append("audio")
    if choices.enable_image:
        extras.append("image")
    if choices.enable_video:
        extras.append("video")
    if choices.enable_rerank_ane and env.host.is_apple_silicon:
        extras.append("ANE rerank")

    pro_features = []
    if choices.edition == "pro":
        if choices.enable_multi_tenant:
            pro_features.append("multi-tenant")
        if choices.enable_sync:
            pro_features.append("sync")
        if choices.enable_smart_observer:
            pro_features.append("smart observer")

    feature_str = ", ".join(extras) if extras else "core only"
    pro_str = (
        (f" + Pro ({', '.join(pro_features)})" if pro_features else "")
        if choices.edition == "pro"
        else ""
    )

    return (
        f"RecordorAI {choices.edition}{pro_str} → "
        f"{choices.runtime} runtime, palace at {choices.palace_root}, "
        f"features: {feature_str}. {len(plan)} steps."
    )
