"""Plan executor — runs steps in order, rolls back on failure.

The executor is UI-agnostic: it emits :class:`ExecEvent` objects that
the TUI / Tauri front-ends translate into progress bars, log lines,
and error dialogs.

Rollback semantics:

* Each step's ``do`` is called in order.
* If a step raises, the executor calls ``undo`` for **already-completed**
  steps in reverse order (best-effort — undo failures are logged but
  don't stop the rollback).
* Verify-kind steps that record ``passes=False`` in metadata also
  trigger rollback unless ``allow_warn=True`` is set.

Reserved for later: pause/resume support, dry-run, parallel-step
graphs. Sprint 1 ships the linear case.
"""

from __future__ import annotations

import logging
import time
import traceback
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from .plan import Plan, Step

log = logging.getLogger("recordorai_installer.core.exec")


# ──────────────────────────────────────────────────────────────────────────
# Events the executor emits
# ──────────────────────────────────────────────────────────────────────────


class EventType(str, Enum):
    PLAN_START = "plan_start"
    STEP_START = "step_start"
    STEP_OK = "step_ok"
    STEP_WARN = "step_warn"
    STEP_FAIL = "step_fail"
    ROLLBACK_START = "rollback_start"
    ROLLBACK_STEP = "rollback_step"
    ROLLBACK_DONE = "rollback_done"
    PLAN_OK = "plan_ok"
    PLAN_FAIL = "plan_fail"


@dataclass
class ExecEvent:
    type: EventType
    step: Step | None = None
    index: int = -1
    total: int = 0
    message: str = ""
    error: BaseException | None = None
    elapsed_s: float = 0.0


# ──────────────────────────────────────────────────────────────────────────
# Result
# ──────────────────────────────────────────────────────────────────────────


@dataclass
class ExecResult:
    success: bool
    completed_steps: list[Step] = field(default_factory=list)
    failed_step: Step | None = None
    error: BaseException | None = None
    elapsed_s: float = 0.0


# ──────────────────────────────────────────────────────────────────────────
# Executor
# ──────────────────────────────────────────────────────────────────────────


def execute(
    plan: Plan,
    *,
    on_event: Callable[[ExecEvent], None] | None = None,
    allow_warn: bool = False,
) -> ExecResult:
    """Run every step in the plan; roll back on failure.

    Parameters
    ----------
    plan:
        The :class:`Plan` produced by :func:`recordorai_installer.core.plan.build_plan`.
    on_event:
        Optional callback invoked for every :class:`ExecEvent`. The
        TUI's progress widget subscribes here.
    allow_warn:
        If True, verify-kind steps whose metadata reports
        ``passes=False`` only emit STEP_WARN and the plan continues.
        If False (default), the same condition aborts and rolls back.
    """
    on_event = on_event or (lambda _e: None)
    completed: list[Step] = []
    started = time.monotonic()
    total = len(plan)

    on_event(ExecEvent(type=EventType.PLAN_START, total=total))

    for idx, step in enumerate(plan.steps):
        step_start = time.monotonic()
        on_event(ExecEvent(type=EventType.STEP_START, step=step, index=idx, total=total))

        try:
            ok = _run_step(step, on_event, idx, total, allow_warn=allow_warn)
        except Exception as e:  # noqa: BLE001 — we want every failure caught
            tb = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            log.error("step %d (%s) failed:\n%s", idx, step.title, tb)
            on_event(
                ExecEvent(
                    type=EventType.STEP_FAIL,
                    step=step,
                    index=idx,
                    total=total,
                    error=e,
                    message=str(e),
                    elapsed_s=time.monotonic() - step_start,
                )
            )
            _rollback(completed, on_event)
            on_event(
                ExecEvent(
                    type=EventType.PLAN_FAIL,
                    error=e,
                    elapsed_s=time.monotonic() - started,
                )
            )
            return ExecResult(
                success=False,
                completed_steps=completed,
                failed_step=step,
                error=e,
                elapsed_s=time.monotonic() - started,
            )

        if not ok:
            # Verify-step soft-failure with allow_warn=False is treated
            # like a hard failure — same rollback path.
            err = RuntimeError(f"Verification failed: {step.title}. {step.detail}")
            on_event(
                ExecEvent(
                    type=EventType.STEP_FAIL,
                    step=step,
                    index=idx,
                    total=total,
                    error=err,
                    message=str(err),
                    elapsed_s=time.monotonic() - step_start,
                )
            )
            _rollback(completed, on_event)
            on_event(
                ExecEvent(
                    type=EventType.PLAN_FAIL,
                    error=err,
                    elapsed_s=time.monotonic() - started,
                )
            )
            return ExecResult(
                success=False,
                completed_steps=completed,
                failed_step=step,
                error=err,
                elapsed_s=time.monotonic() - started,
            )

        completed.append(step)
        on_event(
            ExecEvent(
                type=EventType.STEP_OK,
                step=step,
                index=idx,
                total=total,
                elapsed_s=time.monotonic() - step_start,
            )
        )

    elapsed = time.monotonic() - started
    on_event(ExecEvent(type=EventType.PLAN_OK, total=total, elapsed_s=elapsed))
    return ExecResult(success=True, completed_steps=completed, elapsed_s=elapsed)


# ──────────────────────────────────────────────────────────────────────────
# Internals
# ──────────────────────────────────────────────────────────────────────────


def _run_step(
    step: Step,
    on_event: Callable[[ExecEvent], None],
    index: int,
    total: int,
    *,
    allow_warn: bool,
) -> bool:
    """Run one step. Returns ``True`` if it succeeded; ``False`` for a
    soft failure that should propagate as STEP_FAIL.

    Verify steps with ``passes=False`` and ``allow_warn=True`` emit
    STEP_WARN and return ``True``.
    """
    if step.kind == "verify":
        passes = bool(step.metadata.get("passes", True))
        if not passes:
            if allow_warn:
                on_event(
                    ExecEvent(
                        type=EventType.STEP_WARN,
                        step=step,
                        index=index,
                        total=total,
                        message=step.detail,
                    )
                )
                return True
            return False
        # If ``passes`` isn't yet recorded (computed at exec time), the
        # step's ``do`` callback is responsible for setting it.
        if step.do is not None:
            step.do()
            passes = bool(step.metadata.get("passes", True))
            if not passes and not allow_warn:
                return False
        return True

    if step.do is None:
        # Pure-data step (used in tests + plan-preview UI).
        return True

    step.do()
    return True


def _rollback(
    completed: list[Step],
    on_event: Callable[[ExecEvent], None],
) -> None:
    """Best-effort reverse-order undo of every completed step."""
    on_event(ExecEvent(type=EventType.ROLLBACK_START, total=len(completed)))
    for idx, step in enumerate(reversed(completed)):
        if step.undo is None:
            continue
        try:
            step.undo()
        except Exception as e:  # noqa: BLE001
            log.warning("undo for %r failed: %s", step.title, e)
            on_event(
                ExecEvent(
                    type=EventType.ROLLBACK_STEP,
                    step=step,
                    index=idx,
                    total=len(completed),
                    error=e,
                    message=f"undo failed: {e}",
                )
            )
        else:
            on_event(
                ExecEvent(
                    type=EventType.ROLLBACK_STEP,
                    step=step,
                    index=idx,
                    total=len(completed),
                    message="undone",
                )
            )
    on_event(ExecEvent(type=EventType.ROLLBACK_DONE, total=len(completed)))


# ──────────────────────────────────────────────────────────────────────────
# Iterator helper for the TUI's "stream events" pattern
# ──────────────────────────────────────────────────────────────────────────


def execute_streaming(plan: Plan, *, allow_warn: bool = False) -> Iterator[ExecEvent]:
    """Yield :class:`ExecEvent` instances as the plan executes.

    The TUI uses this in a Textual worker so the UI thread can update
    progress widgets without blocking. Tauri uses the JSON-RPC bridge
    which calls :func:`execute` with an ``on_event`` callback that
    forwards to the front-end — both surfaces share the same event
    schema.
    """
    events: list[ExecEvent] = []

    def collect(event: ExecEvent) -> None:
        events.append(event)

    # We can't truly stream from execute() without threading; for
    # Sprint 1 we collect and yield in batch. Sprint 2's Tauri bridge
    # will use a worker thread + queue for true streaming.
    execute(plan, on_event=collect, allow_warn=allow_warn)
    yield from events
