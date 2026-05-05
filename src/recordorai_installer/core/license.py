"""License validation — Pro monthly subscription.

Sprint 1 ships the local logic + caching + grace-period rules. The
actual server-side validation endpoint is wired in Sprint 5; for now
:func:`validate_online` calls a swappable
:class:`LicenseClient.check_subscription` method that's stubbed in
tests and pluggable in production.

State machine:

    NEW                                 (no key entered yet)
     │   user enters key
     ▼
    VALIDATING (online)
     │   ├─ server: active → ACTIVE
     │   ├─ server: expired → EXPIRED
     │   ├─ server: unknown → INVALID
     │   └─ network failure → cached state if grace OK, else GRACE_EXPIRED
     ▼
    ACTIVE (subscription paid, runs offline within grace_days)

The validator caches the last successful "active" timestamp in
``installer_data_dir() / license.json`` so the user doesn't need
internet on every launch. The grace period (default 7 days) keeps a
user productive when the license server is unreachable; after that
Pro features lock until the next successful validation.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol

from .detect import installer_data_dir

log = logging.getLogger("recordorai_installer.core.license")


# ──────────────────────────────────────────────────────────────────────────
# Data
# ──────────────────────────────────────────────────────────────────────────


class LicenseState(str, Enum):
    NEW = "new"
    ACTIVE = "active"
    GRACE = "grace"  # offline, within grace window
    GRACE_EXPIRED = "grace_expired"
    EXPIRED = "expired"
    INVALID = "invalid"


@dataclass
class LicenseStatus:
    state: LicenseState
    edition: str  # "community" | "pro"
    plan: str = ""  # "pro_monthly" | "trial" etc., as returned by server
    last_validated_iso: str | None = None
    expires_iso: str | None = None
    grace_days_remaining: int | None = None
    customer_email: str | None = None
    message: str = ""


# ──────────────────────────────────────────────────────────────────────────
# Network shim — concrete client wired in Sprint 5
# ──────────────────────────────────────────────────────────────────────────


class LicenseClient(Protocol):
    """Anything that can answer 'is this key currently valid?'.

    The Sprint 5 implementation will hit the chosen payment processor
    (Lemon Squeezy / Paddle / Stripe Billing) or Keygen.sh. For
    Sprint 1 the TUI uses :class:`StubLicenseClient` so the wizard can
    be exercised end-to-end in tests.
    """

    def check_subscription(self, license_key: str) -> ServerResponse: ...


@dataclass
class ServerResponse:
    valid: bool
    plan: str = ""  # e.g. "pro_monthly"
    expires_iso: str | None = None
    customer_email: str | None = None
    message: str = ""


class StubLicenseClient:
    """Test-only client. The TUI's "Sprint 1 demo" mode swaps this in
    so the wizard can complete a Pro install without a real backend.

    Recognized keys:

    * ``RAI-PRO-VALID-XXXX`` → active subscription
    * ``RAI-PRO-EXPIRED-XXXX`` → expired subscription
    * any other key → invalid
    """

    def check_subscription(self, license_key: str) -> ServerResponse:
        key = (license_key or "").strip().upper()
        if key.startswith("RAI-PRO-VALID"):
            tomorrow = _dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(days=30)
            return ServerResponse(
                valid=True,
                plan="pro_monthly",
                expires_iso=tomorrow.isoformat(),
                customer_email="demo@recordorai.com",
                message="Active monthly subscription.",
            )
        if key.startswith("RAI-PRO-EXPIRED"):
            past = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=2)
            return ServerResponse(
                valid=False,
                plan="pro_monthly",
                expires_iso=past.isoformat(),
                customer_email="demo@recordorai.com",
                message="Subscription expired; please renew at recordorai.com/pro.",
            )
        return ServerResponse(
            valid=False,
            message="License key not recognized.",
        )


# ──────────────────────────────────────────────────────────────────────────
# Local cache
# ──────────────────────────────────────────────────────────────────────────


def _cache_path() -> Path:
    base = installer_data_dir()
    base.mkdir(parents=True, exist_ok=True)
    return base / "license.json"


def _load_cache() -> dict | None:
    p = _cache_path()
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _save_cache(status: LicenseStatus) -> None:
    p = _cache_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(asdict(status), indent=2), encoding="utf-8")


def clear_cache() -> None:
    """Wipe the cache — used by uninstall and by tests."""
    p = _cache_path()
    try:
        p.unlink()
    except FileNotFoundError:
        pass


# ──────────────────────────────────────────────────────────────────────────
# Validation entry points
# ──────────────────────────────────────────────────────────────────────────


def _default_client() -> LicenseClient:
    """Pick the configured license-client backend.

    Honours ``RECORDORAI_LICENSE_BACKEND`` (lemonsqueezy / keygen /
    generic), falling back to lemonsqueezy.

    Tests that don't want a real network round-trip pass
    ``client=StubLicenseClient()`` to :func:`validate_online`
    directly.
    """
    # Local import — keeps the license module importable in
    # environments that don't have httpx (TUI start-up shouldn't
    # require it just to read the cached status).
    from .license_clients import get_client

    return get_client()


def validate_online(
    license_key: str,
    *,
    client: LicenseClient | None = None,
) -> LicenseStatus:
    """Validate the key against the license server. Updates the local
    cache on success.

    Returns the resulting :class:`LicenseStatus`. Doesn't raise —
    network failures fall through to :func:`validate_offline`.
    """
    client = client or _default_client()
    try:
        resp = client.check_subscription(license_key)
    except Exception as e:  # noqa: BLE001 — network call may fail any way
        log.warning("license server unreachable: %s", e)
        return validate_offline(license_key)

    now = _dt.datetime.now(_dt.timezone.utc).isoformat()

    if resp.valid:
        status = LicenseStatus(
            state=LicenseState.ACTIVE,
            edition="pro",
            plan=resp.plan,
            last_validated_iso=now,
            expires_iso=resp.expires_iso,
            customer_email=resp.customer_email,
            message=resp.message or "Subscription active.",
        )
        _save_cache(status)
        return status

    # Distinguish expired (we know about the key) from invalid (we don't).
    if resp.plan or resp.expires_iso:
        return LicenseStatus(
            state=LicenseState.EXPIRED,
            edition="community",  # fallback — user keeps free features
            plan=resp.plan,
            expires_iso=resp.expires_iso,
            message=resp.message or "Subscription has expired.",
        )

    return LicenseStatus(
        state=LicenseState.INVALID,
        edition="community",
        message=resp.message or "License key not recognized.",
    )


def validate_offline(license_key: str | None, *, grace_days: int = 7) -> LicenseStatus:
    """Validate using the local cache only.

    Used at app startup to avoid blocking on the network, and as a
    fallback when :func:`validate_online` can't reach the server.
    """
    cached = _load_cache()
    if not cached:
        return LicenseStatus(
            state=LicenseState.NEW,
            edition="community",
            message="No license cached. Continue with Community edition.",
        )

    last_iso = cached.get("last_validated_iso")
    if not last_iso:
        return LicenseStatus(
            state=LicenseState.INVALID,
            edition="community",
            message="License cache is malformed.",
        )

    try:
        last = _dt.datetime.fromisoformat(last_iso)
    except ValueError:
        return LicenseStatus(
            state=LicenseState.INVALID,
            edition="community",
            message="License cache timestamp is unreadable.",
        )

    now = _dt.datetime.now(_dt.timezone.utc)
    if last.tzinfo is None:
        last = last.replace(tzinfo=_dt.timezone.utc)
    age_days = (now - last).days

    if age_days <= grace_days:
        return LicenseStatus(
            state=LicenseState.ACTIVE if age_days == 0 else LicenseState.GRACE,
            edition="pro",
            plan=cached.get("plan", "pro_monthly"),
            last_validated_iso=last_iso,
            expires_iso=cached.get("expires_iso"),
            grace_days_remaining=grace_days - age_days,
            customer_email=cached.get("customer_email"),
            message=(
                "Cached license is fresh."
                if age_days == 0
                else f"Offline mode; {grace_days - age_days} day(s) of grace remaining."
            ),
        )

    return LicenseStatus(
        state=LicenseState.GRACE_EXPIRED,
        edition="community",
        plan=cached.get("plan", ""),
        last_validated_iso=last_iso,
        message=(
            "Offline grace expired. Reconnect to revalidate your "
            "subscription, or continue with Community edition."
        ),
    )


# ──────────────────────────────────────────────────────────────────────────
# Helper used by the wizard's "Edition" screen
# ──────────────────────────────────────────────────────────────────────────


def gate(feature: str, status: LicenseStatus) -> bool:
    """Return True iff the requested Pro feature should be enabled
    given the current license state.

    Pro features are blocked unless ``status.state`` is ACTIVE or GRACE.
    EXPIRED, GRACE_EXPIRED, INVALID, NEW all block.
    """
    pro_features = {"multi_tenant", "sync", "smart_observer"}
    if feature not in pro_features:
        return True  # Community feature — always allowed.

    return status.state in (LicenseState.ACTIVE, LicenseState.GRACE)
