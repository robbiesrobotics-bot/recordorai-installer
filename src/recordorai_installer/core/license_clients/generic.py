"""GenericHttpLicenseClient — for self-hosted license servers.

If you don't want to use Lemon Squeezy or Keygen and prefer to host
your own license server, the contract is small:

    POST $RECORDORAI_LICENSE_URL/v1/licenses/validate
    Headers:
        Authorization: Bearer $RECORDORAI_LICENSE_TOKEN  (optional)
        Content-Type: application/json
    Body:
        {
          "license_key": "...",
          "instance_id": "..."   (optional — sent only after activation)
        }
    Response (200 OK):
        {
          "valid": true | false,
          "plan": "pro_monthly" | "...",
          "expires_iso": "2026-06-12T00:00:00Z",
          "customer_email": "user@example.com",
          "message": "Subscription active."
        }

Anything that speaks that contract works. Sample server
implementations live in ``docs/licensing.md``.

Configuration via env:

    RECORDORAI_LICENSE_URL          (required for generic backend)
    RECORDORAI_LICENSE_TOKEN        (optional bearer)
"""

from __future__ import annotations

import logging
import os

import httpx

from ..license import ServerResponse

log = logging.getLogger("recordorai_installer.core.license_clients.generic")


_TIMEOUT_S = 10.0


class GenericHttpLicenseClient:
    """Concrete :class:`LicenseClient` for self-hosted license servers."""

    def __init__(
        self,
        *,
        url: str | None = None,
        token: str | None = None,
        timeout_s: float = _TIMEOUT_S,
        instance_id: str | None = None,
    ) -> None:
        self._url = (url or os.environ.get("RECORDORAI_LICENSE_URL", "")).rstrip("/")
        self._token = token or os.environ.get("RECORDORAI_LICENSE_TOKEN", "")
        self._timeout_s = timeout_s
        self._instance_id = instance_id

        if not self._url:
            log.warning(
                "Generic backend selected but RECORDORAI_LICENSE_URL is "
                "unset — validation calls will fail. Set the env var or "
                "switch backend with RECORDORAI_LICENSE_BACKEND=lemonsqueezy."
            )

    # ── LicenseClient Protocol ────────────────────────────────────────

    def check_subscription(self, license_key: str) -> ServerResponse:
        if not self._url:
            return ServerResponse(
                valid=False,
                message=(
                    "Generic backend requires RECORDORAI_LICENSE_URL. "
                    "Set it (e.g. https://license.example.com) or use "
                    "the lemonsqueezy backend."
                ),
            )

        body: dict = {"license_key": license_key}
        if self._instance_id:
            body["instance_id"] = self._instance_id

        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        try:
            with httpx.Client(timeout=self._timeout_s) as client:
                r = client.post(
                    f"{self._url}/v1/licenses/validate",
                    json=body,
                    headers=headers,
                )
        except httpx.HTTPError as e:
            log.warning("Generic license server unreachable: %s", e)
            raise

        try:
            payload = r.json()
        except ValueError as e:
            raise httpx.HTTPError(f"License server returned non-JSON: {r.text[:200]!r}") from e

        return ServerResponse(
            valid=bool(payload.get("valid")),
            plan=str(payload.get("plan") or ""),
            expires_iso=payload.get("expires_iso"),
            customer_email=payload.get("customer_email"),
            message=str(payload.get("message") or ""),
        )
