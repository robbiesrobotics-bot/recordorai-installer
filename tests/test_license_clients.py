"""Tests for the concrete LicenseClient backends.

httpx is mocked via ``MockTransport`` so these tests run without
network access. Each backend gets:

* a happy-path validate response → translates to ServerResponse(valid=True)
* an explicit "invalid" response → ServerResponse(valid=False) with metadata
* a network failure → httpx.HTTPError propagates so license.py falls
  back to validate_offline()

The selector is exercised separately — env-var → backend mapping.
"""

from __future__ import annotations

import httpx
import pytest

# ──────────────────────────────────────────────────────────────────────────
# Selector
# ──────────────────────────────────────────────────────────────────────────


class TestSelector:
    def test_default_is_lemonsqueezy(self, monkeypatch):
        monkeypatch.delenv("RECORDORAI_LICENSE_BACKEND", raising=False)
        from recordorai_installer.core.license_clients import default_backend_name

        assert default_backend_name() == "lemonsqueezy"

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("lemonsqueezy", "lemonsqueezy"),
            ("LEMONSQUEEZY", "lemonsqueezy"),
            (" keygen ", "keygen"),
            ("generic", "generic"),
            ("nonsense-value", "lemonsqueezy"),  # falls back
        ],
    )
    def test_env_var_picks_backend(self, monkeypatch, value, expected):
        monkeypatch.setenv("RECORDORAI_LICENSE_BACKEND", value)
        from recordorai_installer.core.license_clients import default_backend_name

        assert default_backend_name() == expected

    def test_supported_backends_lists_all(self):
        from recordorai_installer.core.license_clients import supported_backends

        assert sorted(supported_backends()) == ["generic", "keygen", "lemonsqueezy"]

    def test_get_client_returns_instance(self, monkeypatch):
        monkeypatch.delenv("RECORDORAI_KEYGEN_ACCOUNT", raising=False)
        from recordorai_installer.core.license_clients import get_client

        for name in ("lemonsqueezy", "keygen", "generic"):
            client = get_client(name)
            # The Protocol has no isinstance check, but every
            # backend exposes check_subscription(license_key).
            assert callable(getattr(client, "check_subscription", None))

    def test_get_client_raises_for_unknown(self):
        from recordorai_installer.core.license_clients import get_client

        with pytest.raises(KeyError):
            get_client("not-a-backend")


# ──────────────────────────────────────────────────────────────────────────
# httpx mocking helper
# ──────────────────────────────────────────────────────────────────────────


def _make_client(backend_cls, *, status_code: int, response_body: dict | str):
    """Build a backend instance whose internal httpx.Client uses a
    mocked transport returning the canned response.

    We swap the module-level ``httpx.Client`` constructor with a
    factory that injects ``transport=MockTransport(...)``. This is
    less invasive than monkeypatching the backend's private _post.
    """

    def _handler(_request: httpx.Request) -> httpx.Response:
        if isinstance(response_body, dict):
            return httpx.Response(
                status_code,
                json=response_body,
                headers={"content-type": "application/json"},
            )
        return httpx.Response(
            status_code,
            content=response_body.encode(),
            headers={"content-type": "text/plain"},
        )

    transport = httpx.MockTransport(_handler)

    class _PatchedClient(httpx.Client):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("transport", transport)
            super().__init__(*args, **kwargs)

    return backend_cls, _PatchedClient


# ──────────────────────────────────────────────────────────────────────────
# LemonSqueezyClient
# ──────────────────────────────────────────────────────────────────────────


_LS_VALID_PAYLOAD = {
    "valid": True,
    "license_key": {
        "id": 1,
        "status": "active",
        "key": "RAI-PRO-XXXX-XXXX",
        "expires_at": "2027-01-01T00:00:00.000000Z",
    },
    "instance": {"id": "inst-abc", "name": "alice-mac"},
    "meta": {
        "store_id": 1,
        "product_id": 1,
        "variant_id": 1,
        "variant_name": "Pro Monthly",
        "customer_email": "alice@example.com",
        "customer_name": "Alice",
    },
}

_LS_INVALID_PAYLOAD = {
    "valid": False,
    "license_key": {
        "id": 1,
        "status": "expired",
        "key": "RAI-PRO-XXXX-XXXX",
        "expires_at": "2024-01-01T00:00:00.000000Z",
    },
    "instance": None,
    "meta": {"variant_name": "Pro Monthly"},
}


class TestLemonSqueezyClient:
    def test_valid_response_translates_to_active(self, monkeypatch):
        from recordorai_installer.core.license_clients import lemonsqueezy as ls_mod

        cls, patched_client = _make_client(
            ls_mod.LemonSqueezyClient,
            status_code=200,
            response_body=_LS_VALID_PAYLOAD,
        )
        monkeypatch.setattr(ls_mod, "httpx", _module_with(patched_client))

        client = cls()
        resp = client.check_subscription("RAI-PRO-VALID-1234")

        assert resp.valid is True
        assert resp.plan == "Pro Monthly"
        assert resp.expires_iso == "2027-01-01T00:00:00.000000Z"
        assert resp.customer_email == "alice@example.com"

    def test_invalid_response_translates_to_invalid(self, monkeypatch):
        from recordorai_installer.core.license_clients import lemonsqueezy as ls_mod

        cls, patched_client = _make_client(
            ls_mod.LemonSqueezyClient,
            status_code=200,
            response_body=_LS_INVALID_PAYLOAD,
        )
        monkeypatch.setattr(ls_mod, "httpx", _module_with(patched_client))

        client = cls()
        resp = client.check_subscription("anything")

        assert resp.valid is False
        assert "expired" in resp.message.lower() or resp.expires_iso

    def test_5xx_raises_httperror_so_license_module_falls_back(self, monkeypatch):
        from recordorai_installer.core.license_clients import lemonsqueezy as ls_mod

        cls, patched_client = _make_client(
            ls_mod.LemonSqueezyClient,
            status_code=503,
            response_body={"error": "service unavailable"},
        )
        monkeypatch.setattr(ls_mod, "httpx", _module_with(patched_client))

        client = cls()
        with pytest.raises(httpx.HTTPError):
            client.check_subscription("anything")

    def test_non_json_response_raises_httperror(self, monkeypatch):
        from recordorai_installer.core.license_clients import lemonsqueezy as ls_mod

        cls, patched_client = _make_client(
            ls_mod.LemonSqueezyClient,
            status_code=200,
            response_body="Bad Gateway HTML",
        )
        monkeypatch.setattr(ls_mod, "httpx", _module_with(patched_client))

        client = cls()
        with pytest.raises(httpx.HTTPError):
            client.check_subscription("anything")

    def test_activate_returns_raw_payload(self, monkeypatch):
        from recordorai_installer.core.license_clients import lemonsqueezy as ls_mod

        cls, patched_client = _make_client(
            ls_mod.LemonSqueezyClient,
            status_code=200,
            response_body=_LS_VALID_PAYLOAD,
        )
        monkeypatch.setattr(ls_mod, "httpx", _module_with(patched_client))

        client = cls()
        out = client.activate("RAI-PRO-VALID-1234", "alice-mac")
        assert out["instance"]["id"] == "inst-abc"


# ──────────────────────────────────────────────────────────────────────────
# KeygenClient
# ──────────────────────────────────────────────────────────────────────────


_KEYGEN_VALID_PAYLOAD = {
    "data": {
        "id": "lic-1",
        "type": "licenses",
        "attributes": {
            "name": "Pro Monthly",
            "status": "ACTIVE",
            "expiry": "2027-01-01T00:00:00.000Z",
        },
    },
    "meta": {"valid": True, "status": "ACTIVE"},
}

_KEYGEN_INVALID_PAYLOAD = {
    "data": None,
    "meta": {"valid": False, "status": "EXPIRED"},
    "errors": [{"detail": "License has expired"}],
}


class TestKeygenClient:
    def test_unconfigured_returns_invalid_with_message(self, monkeypatch):
        monkeypatch.delenv("RECORDORAI_KEYGEN_ACCOUNT", raising=False)
        monkeypatch.delenv("RECORDORAI_KEYGEN_PRODUCT", raising=False)

        from recordorai_installer.core.license_clients import keygen as kg_mod

        client = kg_mod.KeygenClient()
        resp = client.check_subscription("anything")
        assert resp.valid is False
        assert "RECORDORAI_KEYGEN_ACCOUNT" in resp.message

    def test_valid_response_translates_to_active(self, monkeypatch):
        from recordorai_installer.core.license_clients import keygen as kg_mod

        cls, patched_client = _make_client(
            kg_mod.KeygenClient,
            status_code=200,
            response_body=_KEYGEN_VALID_PAYLOAD,
        )
        monkeypatch.setattr(kg_mod, "httpx", _module_with(patched_client))
        monkeypatch.setenv("RECORDORAI_KEYGEN_ACCOUNT", "acc-1")

        client = cls(account_id="acc-1")
        resp = client.check_subscription("RAI-PRO-VALID")

        assert resp.valid is True
        assert resp.plan == "Pro Monthly"
        assert resp.expires_iso == "2027-01-01T00:00:00.000Z"

    def test_invalid_response_carries_error_detail(self, monkeypatch):
        from recordorai_installer.core.license_clients import keygen as kg_mod

        cls, patched_client = _make_client(
            kg_mod.KeygenClient,
            status_code=200,
            response_body=_KEYGEN_INVALID_PAYLOAD,
        )
        monkeypatch.setattr(kg_mod, "httpx", _module_with(patched_client))

        client = cls(account_id="acc-1")
        resp = client.check_subscription("expired-key")
        assert resp.valid is False
        assert "expired" in resp.message.lower()


# ──────────────────────────────────────────────────────────────────────────
# GenericHttpLicenseClient
# ──────────────────────────────────────────────────────────────────────────


_GENERIC_VALID = {
    "valid": True,
    "plan": "pro_monthly",
    "expires_iso": "2027-01-01T00:00:00Z",
    "customer_email": "alice@example.com",
    "message": "OK",
}

_GENERIC_INVALID = {
    "valid": False,
    "plan": "pro_monthly",
    "message": "Subscription cancelled.",
}


class TestGenericHttpLicenseClient:
    def test_unconfigured_returns_invalid_with_message(self, monkeypatch):
        monkeypatch.delenv("RECORDORAI_LICENSE_URL", raising=False)
        monkeypatch.delenv("RECORDORAI_LICENSE_TOKEN", raising=False)

        from recordorai_installer.core.license_clients import generic as gen_mod

        client = gen_mod.GenericHttpLicenseClient()
        resp = client.check_subscription("anything")
        assert resp.valid is False
        assert "RECORDORAI_LICENSE_URL" in resp.message

    def test_valid_response_passes_through(self, monkeypatch):
        from recordorai_installer.core.license_clients import generic as gen_mod

        cls, patched_client = _make_client(
            gen_mod.GenericHttpLicenseClient,
            status_code=200,
            response_body=_GENERIC_VALID,
        )
        monkeypatch.setattr(gen_mod, "httpx", _module_with(patched_client))

        client = cls(url="https://license.example.com")
        resp = client.check_subscription("RAI-PRO-VALID")

        assert resp.valid is True
        assert resp.plan == "pro_monthly"
        assert resp.customer_email == "alice@example.com"

    def test_invalid_response_passes_message(self, monkeypatch):
        from recordorai_installer.core.license_clients import generic as gen_mod

        cls, patched_client = _make_client(
            gen_mod.GenericHttpLicenseClient,
            status_code=200,
            response_body=_GENERIC_INVALID,
        )
        monkeypatch.setattr(gen_mod, "httpx", _module_with(patched_client))

        client = cls(url="https://license.example.com")
        resp = client.check_subscription("anything")
        assert resp.valid is False
        assert "cancelled" in resp.message.lower()


# ──────────────────────────────────────────────────────────────────────────
# httpx swap helper
# ──────────────────────────────────────────────────────────────────────────


def _module_with(patched_client_cls):
    """Build a stand-in for the ``httpx`` module that exposes the
    same surface our backends use, but with our patched Client.

    Each backend imports ``httpx`` at module level and uses
    ``httpx.Client``, ``httpx.HTTPError``. We replace the module-level
    name with this object via monkeypatch.setattr so the patched
    Client is used without altering the backend's source.
    """
    import types

    fake = types.SimpleNamespace(
        Client=patched_client_cls,
        HTTPError=httpx.HTTPError,
        MockTransport=httpx.MockTransport,
        Response=httpx.Response,
        Request=httpx.Request,
    )
    return fake
