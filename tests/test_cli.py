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

    def test_rpc_flag_returns_2_in_sprint_1(self, capsys):
        rc = main(["--rpc"])
        err = capsys.readouterr().err
        assert rc == 2
        assert "Sprint 2" in err or "RPC" in err
