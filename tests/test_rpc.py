"""Tests for recordorai_installer.rpc.server.

End-to-end coverage of the JSON-RPC 2.0 stdio protocol:

* envelope validation (parse error, invalid version, missing method)
* method-not-found for unknown methods
* every public method dispatches and serializes correctly
* streaming notifications during ``installer.execute``
* run() loop reads stdin to EOF and writes responses
"""

from __future__ import annotations

import io
import json

from recordorai_installer.rpc.server import RpcServer
from recordorai_installer.version import __version__


def _server_with_buffers():
    """Helper: build an RpcServer with in-memory stdin/stdout."""
    stdin = io.StringIO("")
    stdout = io.StringIO()
    return RpcServer(stdin=stdin, stdout=stdout), stdin, stdout


def _read_lines(buf: io.StringIO) -> list[dict]:
    buf.seek(0)
    return [json.loads(line) for line in buf if line.strip()]


# ──────────────────────────────────────────────────────────────────────────
# Protocol-level tests
# ──────────────────────────────────────────────────────────────────────────


class TestProtocol:
    def test_parse_error_returns_minus_32700(self):
        srv, _, _ = _server_with_buffers()
        resp = srv.handle_one("not json {")
        assert resp["error"]["code"] == -32700
        assert resp["id"] is None

    def test_missing_jsonrpc_version_is_invalid(self):
        srv, _, _ = _server_with_buffers()
        resp = srv.handle_one(json.dumps({"method": "rpc.ping", "id": 1}))
        assert resp["error"]["code"] == -32600
        assert resp["id"] == 1

    def test_unknown_method_returns_minus_32601(self):
        srv, _, _ = _server_with_buffers()
        resp = srv.handle_one(
            json.dumps({"jsonrpc": "2.0", "id": 5, "method": "rpc.does_not_exist"})
        )
        assert resp["error"]["code"] == -32601
        assert "rpc.does_not_exist" in resp["error"]["message"]

    def test_notification_returns_none(self):
        """Requests without an id field are notifications — no response."""
        srv, _, _ = _server_with_buffers()
        resp = srv.handle_one(json.dumps({"jsonrpc": "2.0", "method": "rpc.ping"}))
        assert resp is None

    def test_blank_lines_are_skipped(self):
        srv, _, _ = _server_with_buffers()
        assert srv.handle_one("") is None
        assert srv.handle_one("   \n") is None


# ──────────────────────────────────────────────────────────────────────────
# Smoke methods
# ──────────────────────────────────────────────────────────────────────────


class TestSmokeMethods:
    def test_ping(self):
        srv, _, _ = _server_with_buffers()
        resp = srv.handle_one(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "rpc.ping"}))
        assert resp["result"] == "pong"

    def test_version(self):
        srv, _, _ = _server_with_buffers()
        resp = srv.handle_one(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "rpc.version"}))
        assert resp["result"] == __version__


# ──────────────────────────────────────────────────────────────────────────
# Installer methods
# ──────────────────────────────────────────────────────────────────────────


class TestInstallerMethods:
    def test_detect_returns_serialized_environment(self):
        srv, _, _ = _server_with_buffers()
        resp = srv.handle_one(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "installer.detect"}))
        env = resp["result"]
        assert isinstance(env, dict)
        assert "host" in env and "python" in env and "runtimes" in env
        assert env["host"]["os"] in ("macos", "linux", "windows", "darwin")
        # No callables / non-JSON values leak through.
        json.dumps(env)  # raises if anything unserializable remains.

    def test_supported_runtimes(self):
        srv, _, _ = _server_with_buffers()
        resp = srv.handle_one(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "installer.supported_runtimes",
                }
            )
        )
        assert sorted(resp["result"]) == sorted(
            ["standalone", "openclaw", "pi-mono", "alice-runtime", "hermes"]
        )

    def test_build_plan_with_choices(self):
        srv, _, _ = _server_with_buffers()
        resp = srv.handle_one(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "installer.build_plan",
                    "params": {
                        "runtime": "standalone",
                        "palace_root": "/tmp/test-palace",
                        "edition": "community",
                        "enable_documents": True,
                    },
                }
            )
        )
        plan = resp["result"]
        assert "summary" in plan and "steps" in plan and "kinds" in plan
        assert any("document-all" in str(s.get("metadata", {})) for s in plan["steps"])

    def test_build_plan_invalid_choices_returns_invalid_params(self):
        srv, _, _ = _server_with_buffers()
        resp = srv.handle_one(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "installer.build_plan",
                    "params": {"completely_unknown_arg": True},
                }
            )
        )
        assert resp["error"]["code"] == -32602  # invalid params

    def test_validate_license_active_key(self, tmp_path, monkeypatch):
        # Isolate the cache so the test doesn't pollute the user's data dir.
        monkeypatch.setattr(
            "recordorai_installer.core.license._cache_path",
            lambda: tmp_path / "license.json",
        )
        srv, _, _ = _server_with_buffers()
        resp = srv.handle_one(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "installer.validate_license",
                    "params": {"license_key": "RAI-PRO-VALID-1234"},
                }
            )
        )
        status = resp["result"]
        assert status["state"] == "active"
        assert status["edition"] == "pro"

    def test_validate_license_offline_no_cache(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "recordorai_installer.core.license._cache_path",
            lambda: tmp_path / "license.json",
        )
        srv, _, _ = _server_with_buffers()
        resp = srv.handle_one(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "installer.validate_license",
                    "params": {"license_key": None, "online": False},
                }
            )
        )
        status = resp["result"]
        assert status["state"] == "new"


# ──────────────────────────────────────────────────────────────────────────
# Streaming execute
# ──────────────────────────────────────────────────────────────────────────


class TestExecuteStreaming:
    def test_execute_emits_install_event_notifications_then_response(self):
        srv, stdin_buf, stdout_buf = _server_with_buffers()

        # Feed a single execute request and EOF.
        stdin_buf.write(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 99,
                    "method": "installer.execute",
                    "params": {
                        "runtime": "standalone",
                        "palace_root": "/tmp/exec-test",
                        "edition": "community",
                        "enable_documents": False,
                        "enable_audio": False,
                        "enable_image": False,
                        "enable_video": False,
                        "enable_rerank_ane": False,
                    },
                }
            )
            + "\n"
        )
        stdin_buf.seek(0)
        srv.run()

        messages = _read_lines(stdout_buf)

        # All but the last should be install.event notifications.
        notifications = [m for m in messages if m.get("method") == "install.event"]
        responses = [m for m in messages if "id" in m and m.get("id") == 99]

        assert len(notifications) >= 2  # PLAN_START + at least one STEP_*
        assert len(responses) == 1
        final = responses[0]
        assert "result" in final
        assert "success" in final["result"]
        assert "elapsed_s" in final["result"]

    def test_install_event_notifications_contain_documented_fields(self):
        srv, stdin_buf, stdout_buf = _server_with_buffers()
        stdin_buf.write(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "installer.execute",
                    "params": {
                        "runtime": "standalone",
                        "palace_root": "/tmp/exec-test",
                    },
                }
            )
            + "\n"
        )
        stdin_buf.seek(0)
        srv.run()

        messages = _read_lines(stdout_buf)
        events = [m for m in messages if m.get("method") == "install.event"]
        assert events, "Expected at least one install.event notification."
        first = events[0]
        params = first["params"]
        # Documented field set:
        for field in ("type", "step_title", "step_kind", "index", "total", "elapsed_s"):
            assert field in params


# ──────────────────────────────────────────────────────────────────────────
# Run loop (stdin → stdout)
# ──────────────────────────────────────────────────────────────────────────


class TestRunLoop:
    def test_run_processes_multiple_messages_then_exits_on_eof(self):
        srv, stdin_buf, stdout_buf = _server_with_buffers()
        stdin_buf.write(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "rpc.ping"}) + "\n")
        stdin_buf.write(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "rpc.version"}) + "\n")
        stdin_buf.seek(0)

        rc = srv.run()
        assert rc == 0

        out = _read_lines(stdout_buf)
        assert out[0]["result"] == "pong"
        assert out[1]["result"] == __version__

    def test_run_on_empty_stdin_exits_immediately(self):
        srv, _, stdout = _server_with_buffers()
        rc = srv.run()
        assert rc == 0
        assert stdout.getvalue() == ""
