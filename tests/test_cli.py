"""Tests for recordorai_installer.cli."""

from __future__ import annotations

import json

from recordorai_installer.cli import main
from recordorai_installer.version import __version__


class TestCli:
    def test_version_flag(self, capsys):
        rc = main(["--version"])
        out = capsys.readouterr().out
        assert rc == 0
        assert __version__ in out

    def test_detect_flag_emits_valid_json(self, capsys):
        rc = main(["--detect"])
        out = capsys.readouterr().out
        assert rc == 0
        payload = json.loads(out)
        assert "host" in payload
        assert "python" in payload
        assert "runtimes" in payload
        assert isinstance(payload["runtimes"], list)

    def test_rpc_flag_runs_jsonrpc_server_and_exits_on_eof(self, monkeypatch):
        """``--rpc`` launches the JSON-RPC server. It returns 0 when
        stdin closes (EOF). Feeding an empty StringIO simulates immediate
        EOF so the server returns without blocking on real stdin.
        """
        import io

        monkeypatch.setattr("sys.stdin", io.StringIO(""))
        rc = main(["--rpc"])
        assert rc == 0
