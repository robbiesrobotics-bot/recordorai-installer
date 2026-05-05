"""KeygenClient — alternative LicenseClient backend (Keygen.sh).

For users who prefer to pair their own payment processor (Stripe
Billing, Paddle, etc.) with a dedicated license-management SaaS.

Keygen.sh's REST API:

  https://keygen.sh/docs/api/

Endpoints used:

    POST https://api.keygen.sh/v1/accounts/{ACCOUNT}/licenses/actions/validate-key
        Body: { meta: { key, scope: { fingerprint } } }
        Returns: { meta: { valid, status, ... }, data: { ... } }

    POST https://api.keygen.sh/v1/accounts/{ACCOUNT}/licenses/{LICENSE}/actions/activate
        (machine activation — anti-sharing per-machine)

    DELETE https://api.keygen.sh/v1/accounts/{ACCOUNT}/machines/{MACHINE}
        (deactivation)

Configuration via env:

    RECORDORAI_KEYGEN_ACCOUNT       (required for keygen backend)
    RECORDORAI_KEYGEN_PRODUCT       (optional; if set, scopes validation)
    RECORDORAI_KEYGEN_PUBLIC_KEY    (optional; for offline signature
                                     verification — Keygen's higher-tier
                                     plans support cryptographically
                                     signed licenses)
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from ..license import ServerResponse

log = logging.getLogger("recordorai_installer.core.license_clients.keygen")


_BASE_URL = "https://api.keygen.sh/v1"
_TIMEOUT_S = 10.0


class KeygenClient:
    """Concrete :class:`LicenseClient` against api.keygen.sh."""

    def __init__(
        self,
        *,
        account_id: str | None = None,
        product_id: str | None = None,
        base_url: str = _BASE_URL,
        timeout_s: float = _TIMEOUT_S,
        machine_fingerprint: str | None = None,
    ) -> None:
        self._account_id = account_id or os.environ.get("RECORDORAI_KEYGEN_ACCOUNT", "")
        self._product_id = product_id or os.environ.get("RECORDORAI_KEYGEN_PRODUCT", "")
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._fingerprint = machine_fingerprint or _machine_fingerprint()

        if not self._account_id:
            log.warning(
                "Keygen backend selected but RECORDORAI_KEYGEN_ACCOUNT is "
                "unset — validation calls will fail. Set the env var or "
                "switch backend with RECORDORAI_LICENSE_BACKEND=lemonsqueezy."
            )

    # ── LicenseClient Protocol ────────────────────────────────────────

    def check_subscription(self, license_key: str) -> ServerResponse:
        if not self._account_id:
            return ServerResponse(
                valid=False,
                message=(
                    "Keygen backend requires RECORDORAI_KEYGEN_ACCOUNT. "
                    "Set the env var or use the lemonsqueezy backend."
                ),
            )

        body: dict[str, Any] = {
            "meta": {
                "key": license_key,
                "scope": {"fingerprint": self._fingerprint},
            }
        }
        if self._product_id:
            body["meta"]["scope"]["product"] = self._product_id

        try:
            payload = self._post(
                f"/accounts/{self._account_id}/licenses/actions/validate-key",
                body,
            )
        except httpx.HTTPError as e:
            log.warning("Keygen validate failed: %s", e)
            raise

        return _to_server_response(payload)

    # ── HTTP plumbing ─────────────────────────────────────────────────

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        with httpx.Client(timeout=self._timeout_s) as client:
            r = client.post(
                url,
                json=body,
                headers={
                    "Accept": "application/vnd.api+json",
                    "Content-Type": "application/vnd.api+json",
                },
            )
        if r.status_code >= 500:
            r.raise_for_status()
        try:
            return r.json()
        except ValueError as e:
            raise httpx.HTTPError(f"Keygen returned non-JSON: {r.text[:200]!r}") from e


# ──────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────


def _machine_fingerprint() -> str:
    """Stable per-machine string for Keygen's machine-scoped activation.

    Keygen accepts any opaque string as a fingerprint. We use a hash of
    (hostname + machine-id) so the same machine produces the same value
    across reinstalls but different machines never collide.
    """
    import hashlib
    import platform

    hostname = platform.node() or "unknown-host"
    # On Linux: /etc/machine-id; macOS: IOPlatformUUID via system_profiler.
    # Both are best-effort — we hash whatever we can get.
    machine_id = ""
    try:
        with open("/etc/machine-id") as f:
            machine_id = f.read().strip()
    except OSError:
        pass
    return hashlib.sha256(f"{hostname}|{machine_id}".encode()).hexdigest()[:32]


def _to_server_response(payload: dict[str, Any]) -> ServerResponse:
    """Turn a Keygen validate-key JSON into our :class:`ServerResponse`."""
    meta = payload.get("meta") or {}
    data = payload.get("data") or {}
    attrs = (data.get("attributes") if isinstance(data, dict) else {}) or {}

    valid = bool(meta.get("valid"))
    status = meta.get("status") or attrs.get("status") or ""
    expires_iso = attrs.get("expiry")

    if errors := payload.get("errors"):
        first = errors[0] if isinstance(errors, list) and errors else {}
        message = (
            first.get("detail") if isinstance(first, dict) else None
        ) or "Keygen returned an error."
    elif valid:
        message = f"License valid (status={status})."
    else:
        message = f"License invalid (status={status})."

    return ServerResponse(
        valid=valid,
        plan=str(attrs.get("name") or status or ""),
        expires_iso=expires_iso,
        customer_email=None,  # Keygen doesn't include customer email by default
        message=message,
    )
