"""Tests for recordorai_installer.core.license."""

from __future__ import annotations

import datetime as _dt

import pytest

from recordorai_installer.core import license as lic_mod


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    """Redirect the license cache to a temp dir per test."""
    fake_cache = tmp_path / "license.json"

    def _fake_path():
        fake_cache.parent.mkdir(parents=True, exist_ok=True)
        return fake_cache

    monkeypatch.setattr(lic_mod, "_cache_path", _fake_path)
    yield


class TestStubClient:
    def test_valid_key_returns_active_subscription(self):
        client = lic_mod.StubLicenseClient()
        resp = client.check_subscription("RAI-PRO-VALID-1234")
        assert resp.valid is True
        assert resp.plan == "pro_monthly"
        assert resp.expires_iso is not None

    def test_expired_key_returns_invalid_with_metadata(self):
        client = lic_mod.StubLicenseClient()
        resp = client.check_subscription("RAI-PRO-EXPIRED-9999")
        assert resp.valid is False
        assert resp.plan == "pro_monthly"

    def test_unknown_key_returns_invalid(self):
        client = lic_mod.StubLicenseClient()
        resp = client.check_subscription("garbage")
        assert resp.valid is False
        assert resp.plan == ""


class TestValidateOnline:
    """validate_online with an explicit StubLicenseClient — the
    network-bearing default backend is exercised separately in
    tests/test_license_clients.py.
    """

    def test_active_key_caches_and_returns_active_state(self):
        status = lic_mod.validate_online("RAI-PRO-VALID-1234", client=lic_mod.StubLicenseClient())
        assert status.state == lic_mod.LicenseState.ACTIVE
        assert status.edition == "pro"
        assert status.last_validated_iso is not None
        # Cache file written.
        assert lic_mod._cache_path().exists()

    def test_expired_key_does_not_unlock_pro(self):
        status = lic_mod.validate_online("RAI-PRO-EXPIRED-9999", client=lic_mod.StubLicenseClient())
        assert status.state == lic_mod.LicenseState.EXPIRED
        assert status.edition == "community"

    def test_unknown_key_returns_invalid(self):
        status = lic_mod.validate_online("garbage", client=lic_mod.StubLicenseClient())
        assert status.state == lic_mod.LicenseState.INVALID
        assert status.edition == "community"

    def test_network_failure_falls_back_to_offline(self, tmp_path):
        class _NoNetClient:
            def check_subscription(self, _key):
                raise OSError("simulated network failure")

        # No prior cache → NEW state.
        status = lic_mod.validate_online("anything", client=_NoNetClient())
        assert status.state == lic_mod.LicenseState.NEW

    def test_network_failure_with_fresh_cache_returns_grace(self):
        # Seed cache with a recent active validation.
        recent = _dt.datetime.now(_dt.timezone.utc).isoformat()
        lic_mod._save_cache(
            lic_mod.LicenseStatus(
                state=lic_mod.LicenseState.ACTIVE,
                edition="pro",
                plan="pro_monthly",
                last_validated_iso=recent,
            )
        )

        class _NoNetClient:
            def check_subscription(self, _key):
                raise OSError("offline")

        status = lic_mod.validate_online("anything", client=_NoNetClient())
        assert status.state in (lic_mod.LicenseState.ACTIVE, lic_mod.LicenseState.GRACE)
        assert status.edition == "pro"


class TestValidateOffline:
    def test_no_cache_returns_new(self):
        status = lic_mod.validate_offline(None)
        assert status.state == lic_mod.LicenseState.NEW
        assert status.edition == "community"

    def test_fresh_cache_returns_active(self):
        now = _dt.datetime.now(_dt.timezone.utc).isoformat()
        lic_mod._save_cache(
            lic_mod.LicenseStatus(
                state=lic_mod.LicenseState.ACTIVE,
                edition="pro",
                plan="pro_monthly",
                last_validated_iso=now,
            )
        )
        status = lic_mod.validate_offline("RAI-PRO-VALID-1234")
        assert status.state == lic_mod.LicenseState.ACTIVE
        assert status.edition == "pro"

    def test_cache_within_grace_returns_grace(self):
        # 3 days ago — within default 7-day grace.
        days_ago = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=3)).isoformat()
        lic_mod._save_cache(
            lic_mod.LicenseStatus(
                state=lic_mod.LicenseState.ACTIVE,
                edition="pro",
                plan="pro_monthly",
                last_validated_iso=days_ago,
            )
        )
        status = lic_mod.validate_offline("anything")
        assert status.state == lic_mod.LicenseState.GRACE
        assert status.edition == "pro"
        assert status.grace_days_remaining == 4

    def test_cache_past_grace_returns_grace_expired(self):
        # 14 days ago — well past 7-day grace.
        days_ago = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=14)).isoformat()
        lic_mod._save_cache(
            lic_mod.LicenseStatus(
                state=lic_mod.LicenseState.ACTIVE,
                edition="pro",
                plan="pro_monthly",
                last_validated_iso=days_ago,
            )
        )
        status = lic_mod.validate_offline("anything")
        assert status.state == lic_mod.LicenseState.GRACE_EXPIRED
        assert status.edition == "community"


class TestGate:
    def test_pro_features_blocked_when_not_active(self):
        s = lic_mod.LicenseStatus(state=lic_mod.LicenseState.NEW, edition="community")
        assert lic_mod.gate("multi_tenant", s) is False
        assert lic_mod.gate("sync", s) is False
        assert lic_mod.gate("smart_observer", s) is False

    def test_pro_features_allowed_in_active_or_grace(self):
        for state in (lic_mod.LicenseState.ACTIVE, lic_mod.LicenseState.GRACE):
            s = lic_mod.LicenseStatus(state=state, edition="pro")
            assert lic_mod.gate("multi_tenant", s) is True
            assert lic_mod.gate("sync", s) is True
            assert lic_mod.gate("smart_observer", s) is True

    def test_community_features_always_allowed(self):
        s = lic_mod.LicenseStatus(state=lic_mod.LicenseState.NEW, edition="community")
        assert lic_mod.gate("documents", s) is True
        assert lic_mod.gate("audio", s) is True


class TestClearCache:
    def test_clear_cache_removes_file(self):
        lic_mod._save_cache(lic_mod.LicenseStatus(state=lic_mod.LicenseState.ACTIVE, edition="pro"))
        assert lic_mod._cache_path().exists()

        lic_mod.clear_cache()
        assert not lic_mod._cache_path().exists()
