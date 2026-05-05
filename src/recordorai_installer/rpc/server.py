"""JSON-RPC server — stdio bridge between the Tauri front-end and the
Python installer core.

Protocol: JSON-RPC 2.0, one message per line of stdin/stdout. We
hand-roll it (no external deps) so the installer package stays small
and starts fast.

Methods exposed to the Tauri client:

  - ``rpc.ping``                       → "pong" (smoke test)
  - ``rpc.version``                    → installer version string
  - ``installer.detect``               → serialized Environment
  - ``installer.supported_runtimes``   → list[str]
  - ``installer.build_plan``           → serialized Plan from Choices
  - ``installer.validate_license``     → serialized LicenseStatus
  - ``installer.execute``              → starts streaming
                                          ``install.event`` notifications;
                                          final response is the ExecResult

Streaming pattern:

    client → {"jsonrpc":"2.0","id":42,"method":"installer.execute",...}
    server → {"jsonrpc":"2.0","method":"install.event","params":{...}}
    server → {"jsonrpc":"2.0","method":"install.event","params":{...}}
    ...
    server → {"jsonrpc":"2.0","id":42,"result":{success:true, ...}}

Errors follow JSON-RPC 2.0's error object shape; method-not-found
returns code -32601, malformed JSON returns -32700.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, is_dataclass
from typing import IO, Any, Callable

from ..adapters import supported_runtimes
from ..core.detect import detect_environment
from ..core.exec_ import execute
from ..core.license import LicenseClient, validate_offline, validate_online
from ..core.plan import Choices, Plan, build_plan
from ..version import __version__

# ──────────────────────────────────────────────────────────────────────────
# JSON-RPC protocol primitives
# ──────────────────────────────────────────────────────────────────────────


_PARSE_ERROR = -32700
_INVALID_REQUEST = -32600
_METHOD_NOT_FOUND = -32601
_INVALID_PARAMS = -32602
_INTERNAL_ERROR = -32603


def _result(req_id: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _error(req_id: Any, code: int, message: str, data: Any = None) -> dict:
    err: dict = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": err}


def _notification(method: str, params: Any) -> dict:
    return {"jsonrpc": "2.0", "method": method, "params": params}


def _serialize(obj: Any) -> Any:
    """JSON-friendly recursive coercion. Handles dataclasses, enums,
    sets, tuples, paths, and bytes (best-effort)."""
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if is_dataclass(obj) and not isinstance(obj, type):
        return _serialize(asdict(obj))
    if hasattr(obj, "value") and hasattr(obj, "name"):
        # Enum-like.
        try:
            return obj.value
        except Exception:  # noqa: BLE001
            pass
    if isinstance(obj, dict):
        return {str(k): _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [_serialize(v) for v in obj]
    if isinstance(obj, BaseException):
        return {"type": type(obj).__name__, "message": str(obj)}
    if hasattr(obj, "__fspath__"):
        return str(obj)
    return repr(obj)


# ──────────────────────────────────────────────────────────────────────────
# Method registry
# ──────────────────────────────────────────────────────────────────────────


class RpcServer:
    """Stdio JSON-RPC server. Single-threaded, synchronous; one message
    at a time. Streaming methods (``installer.execute``) emit
    notifications inline before returning the final response.
    """

    def __init__(
        self,
        *,
        stdin: IO[str] | None = None,
        stdout: IO[str] | None = None,
        license_client: LicenseClient | None = None,
    ) -> None:
        self.stdin = stdin or sys.stdin
        self.stdout = stdout or sys.stdout
        self.license_client = license_client
        self._methods: dict[str, Callable[..., Any]] = {
            "rpc.ping": self._m_ping,
            "rpc.version": self._m_version,
            "installer.detect": self._m_detect,
            "installer.supported_runtimes": self._m_supported_runtimes,
            "installer.build_plan": self._m_build_plan,
            "installer.validate_license": self._m_validate_license,
            "installer.execute": self._m_execute,
        }

    # Public helpers — used by tests + the run() loop.

    def handle_one(self, raw: str) -> dict | None:
        """Parse one stdin line, dispatch, return the response dict
        (or None for notifications without an id).

        Notifications emitted during a streaming method are written
        inline by :meth:`_emit_notification`; this return value is the
        single final response for the call.
        """
        raw = raw.strip()
        if not raw:
            return None
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError as e:
            return _error(None, _PARSE_ERROR, f"Parse error: {e}")

        if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
            return _error(
                msg.get("id") if isinstance(msg, dict) else None,
                _INVALID_REQUEST,
                "Invalid JSON-RPC 2.0 envelope.",
            )

        req_id = msg.get("id")
        method = msg.get("method")
        params = msg.get("params") or {}

        if not isinstance(method, str):
            return _error(req_id, _INVALID_REQUEST, "Missing or non-string method.")

        handler = self._methods.get(method)
        if handler is None:
            return _error(req_id, _METHOD_NOT_FOUND, f"Method not found: {method!r}")

        try:
            if isinstance(params, list):
                result = handler(*params)
            elif isinstance(params, dict):
                result = handler(**params)
            else:
                return _error(req_id, _INVALID_PARAMS, "params must be array or object")
        except TypeError as e:
            # Bad arity / kwargs.
            return _error(req_id, _INVALID_PARAMS, str(e))
        except Exception as e:  # noqa: BLE001
            return _error(req_id, _INTERNAL_ERROR, str(e))

        # Notifications (no id) → no response.
        if req_id is None:
            return None
        return _result(req_id, _serialize(result))

    def run(self) -> int:
        """Read JSON-RPC messages from stdin, write responses to
        stdout, until stdin closes. Returns the exit code (0 on EOF).
        """
        for line in self.stdin:
            response = self.handle_one(line)
            if response is not None:
                self._write(response)
        return 0

    # Internals.

    def _write(self, msg: dict) -> None:
        self.stdout.write(json.dumps(msg) + "\n")
        self.stdout.flush()

    def _emit_notification(self, method: str, params: Any) -> None:
        self._write(_notification(method, _serialize(params)))

    # ── Method handlers ─────────────────────────────────────────────────

    def _m_ping(self) -> str:
        return "pong"

    def _m_version(self) -> str:
        return __version__

    def _m_detect(self) -> dict:
        env = detect_environment()
        return _serialize(env)

    def _m_supported_runtimes(self) -> list[str]:
        return supported_runtimes()

    def _m_build_plan(self, **choices_kwargs: Any) -> dict:
        env = detect_environment()
        choices = Choices(**choices_kwargs)
        plan = build_plan(env, choices)
        return _plan_to_serializable(plan)

    def _m_validate_license(self, license_key: str, *, online: bool = True) -> dict:
        if online:
            status = validate_online(license_key, client=self.license_client)
        else:
            status = validate_offline(license_key)
        return _serialize(status)

    def _m_execute(self, **choices_kwargs: Any) -> dict:
        """Build a plan from choices, execute it, stream events.

        The Tauri client receives ``install.event`` notifications for
        every :class:`recordorai_installer.core.exec_.ExecEvent` while
        the install runs; the final RPC response is the
        :class:`ExecResult` summary.
        """
        env = detect_environment()
        choices = Choices(**choices_kwargs)
        plan = build_plan(env, choices)

        def on_event(ev) -> None:
            self._emit_notification(
                "install.event",
                {
                    "type": ev.type.value if hasattr(ev.type, "value") else str(ev.type),
                    "step_title": ev.step.title if ev.step else None,
                    "step_kind": ev.step.kind if ev.step else None,
                    "index": ev.index,
                    "total": ev.total,
                    "message": ev.message,
                    "elapsed_s": ev.elapsed_s,
                    "error": str(ev.error) if ev.error else None,
                },
            )

        result = execute(plan, on_event=on_event, allow_warn=False)
        return {
            "success": result.success,
            "elapsed_s": result.elapsed_s,
            "completed_count": len(result.completed_steps),
            "failed_step_title": (result.failed_step.title if result.failed_step else None),
            "error": str(result.error) if result.error else None,
        }


def _plan_to_serializable(plan: Plan) -> dict:
    """Plan has Step instances with callable fields — strip those for
    the wire format."""
    return {
        "summary": plan.summary,
        "kinds": plan.kinds(),
        "steps": [
            {
                "kind": s.kind,
                "title": s.title,
                "detail": s.detail,
                "metadata": _serialize(s.metadata),
            }
            for s in plan.steps
        ],
    }


def run(*, license_client: LicenseClient | None = None) -> int:
    """Module-level entry point — used by ``cli.py --rpc``."""
    server = RpcServer(license_client=license_client)
    return server.run()
