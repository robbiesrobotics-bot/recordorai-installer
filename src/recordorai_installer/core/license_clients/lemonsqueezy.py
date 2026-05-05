"""LemonSqueezyClient — default LicenseClient backend.

Talks to Lemon Squeezy's License Keys API:

  https://docs.lemonsqueezy.com/api/license-keys

Endpoints used:

    POST https://api.lemonsqueezy.com/v1/licenses/activate
        Body: license_key, instance_name
        Returns: { license_key: {...}, instance: {id, ...}, meta: {...} }
        Called once per machine on first wizard run; the returned
        instance.id is cached so subsequent runs validate against
        this specific install (anti-key-sharing: if you set the
        product's "License Key Activation Limit" to 3, only 3 active
        machines per key).

    POST https://api.lemonsqueezy.com/v1/licenses/validate
        Body: license_key, [instance_id]
        Returns: { valid: bool, license_key: {...}, ... }
        Called periodically. If the user cancels their subscription,
        Lemon Squeezy marks the key as expired and the next validate
        flips to ``valid: false`` — our cache then transitions to
        EXPIRED on the next call (within the configured grace).

    POST https://api.lemonsqueezy.com/v1/licenses/deactivate
        Body: license_key, instance_id
        Called by the wizard's "Switch machines" / Pro-uninstall flow
        to free up an activation slot.

Auth: license-key endpoints are unauthenticated — the license_key
itself is the secret. We don't hold any service-account token.

This client adapts Lemon Squeezy's response shape to the installer's
:class:`recordorai_installer.core.license.ServerResponse`.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ..license import ServerResponse

log = logging.getLogger("recordorai_installer.core.license_clients.lemonsqueezy")


_BASE_URL = "https://api.lemonsqueezy.com/v1"
_TIMEOUT_S = 10.0


class LemonSqueezyClient:
    """Concrete :class:`LicenseClient` against api.lemonsqueezy.com.

    Stateless. Each call is one HTTPS round-trip. ``check_subscription``
    transparently calls ``validate`` (and falls back to ``activate``
    if the user hasn't been activated on this machine yet — Sprint 5
    leaves activation as a separate explicit call so the wizard can
    show a "Activating on this machine..." progress bar).
    """

    def __init__(
        self,
        *,
        base_url: str = _BASE_URL,
        timeout_s: float = _TIMEOUT_S,
        instance_id: str | None = None,
        instance_name: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._instance_id = instance_id
        self._instance_name = instance_name

    # ── LicenseClient Protocol ────────────────────────────────────────

    def check_subscription(self, license_key: str) -> ServerResponse:
        """Validate the key (with the cached instance_id if present).

        On success the response carries enough metadata that the
        installer's :func:`validate_online` flow can transition to
        ACTIVE. On failure, ``valid=False`` and ``message`` describes
        why.
        """
        try:
            payload = self._post(
                "/licenses/validate",
                {
                    "license_key": license_key,
                    **({"instance_id": self._instance_id} if self._instance_id else {}),
                },
            )
        except httpx.HTTPError as e:
            # The license module catches this and falls back to the
            # cached/grace-mode evaluation.
            log.warning("Lemon Squeezy validate failed: %s", e)
            raise

        return _to_server_response(payload)

    # ── Extra surface used by the wizard ──────────────────────────────

    def activate(self, license_key: str, instance_name: str) -> dict[str, Any]:
        """Activate this machine against the key. Returns the raw LS
        payload so the wizard can extract instance.id and pass it
        back into :func:`__init__` on subsequent invocations.
        """
        payload = self._post(
            "/licenses/activate",
            {"license_key": license_key, "instance_name": instance_name},
        )
        return payload

    def deactivate(self, license_key: str, instance_id: str) -> dict[str, Any]:
        """Free up an activation slot. Used during Pro uninstall and
        when the wizard's 'Switch machines' flow runs.
        """
        return self._post(
            "/licenses/deactivate",
            {"license_key": license_key, "instance_id": instance_id},
        )

    # ── HTTP plumbing ─────────────────────────────────────────────────

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        with httpx.Client(timeout=self._timeout_s) as client:
            r = client.post(
                url,
                data=body,
                headers={
                    "Accept": "application/json",
                    # LS uses application/x-www-form-urlencoded for these
                    # endpoints — httpx auto-detects from `data=`.
                },
            )
        if r.status_code >= 500:
            r.raise_for_status()
        try:
            data = r.json()
        except ValueError as e:
            raise httpx.HTTPError(f"Lemon Squeezy returned non-JSON: {r.text[:200]!r}") from e
        return data


# ──────────────────────────────────────────────────────────────────────────
# Response adaptation
# ──────────────────────────────────────────────────────────────────────────


def _to_server_response(payload: dict[str, Any]) -> ServerResponse:
    """Turn a Lemon Squeezy validate/activate JSON into our generic
    :class:`ServerResponse`.

    LS shape:
        {
          "valid": true,
          "license_key": {
            "id": 1,
            "status": "active",
            "expires_at": "2026-06-12T00:00:00.000000Z",
            ...
          },
          "instance": {"id": "...", "name": "..."} | null,
          "meta": {
            "store_id": ..., "product_id": ..., "variant_id": ...,
            "customer_id": ..., "customer_email": "user@example.com",
            "customer_name": "...",
            "variant_name": "Pro Monthly", ...
          }
        }
    """
    valid = bool(payload.get("valid"))
    license_key = payload.get("license_key") or {}
    meta = payload.get("meta") or {}

    plan = meta.get("variant_name") or ""
    expires_iso = license_key.get("expires_at")
    customer_email = meta.get("customer_email")

    # When the server returns an explicit "error" string, surface it
    # via message; otherwise compose a friendly default.
    error = payload.get("error")
    if error:
        message = str(error)
    elif valid:
        message = "Subscription active."
    else:
        status = license_key.get("status") or "unknown"
        message = f"License is not currently valid (status={status})."

    return ServerResponse(
        valid=valid,
        plan=plan,
        expires_iso=expires_iso,
        customer_email=customer_email,
        message=message,
    )
