"""Concrete :class:`recordorai_installer.core.license.LicenseClient`
implementations.

Sprint 5 ships three:

* :class:`LemonSqueezyClient` — default. Talks directly to
  ``api.lemonsqueezy.com``; no server to host. License-key issuance,
  per-machine instance activation, monthly subscription state are
  all handled by Lemon Squeezy.

* :class:`KeygenClient` — for users who want to self-host the
  license server but pair it with their own payment processor
  (Stripe Billing, etc.). Talks to api.keygen.sh.

* :class:`GenericHttpLicenseClient` — for users who roll their own
  license server. Speaks a small, documented JSON contract so
  white-label deployments don't have to fork our code.

Selection is via the ``RECORDORAI_LICENSE_BACKEND`` env var:

    RECORDORAI_LICENSE_BACKEND=lemonsqueezy  (default)
    RECORDORAI_LICENSE_BACKEND=keygen
    RECORDORAI_LICENSE_BACKEND=generic

Each client supports the same :class:`LicenseClient` Protocol, so
the wizard, the cache, and the validate_online flow are all
backend-agnostic.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..license import LicenseClient


_BACKEND_REGISTRY = {
    "lemonsqueezy": "recordorai_installer.core.license_clients.lemonsqueezy:LemonSqueezyClient",
    "keygen": "recordorai_installer.core.license_clients.keygen:KeygenClient",
    "generic": "recordorai_installer.core.license_clients.generic:GenericHttpLicenseClient",
}


def default_backend_name() -> str:
    """Return the active backend name, picked from
    ``RECORDORAI_LICENSE_BACKEND`` with a fallback to
    ``"lemonsqueezy"``.
    """
    raw = os.environ.get("RECORDORAI_LICENSE_BACKEND", "lemonsqueezy").strip().lower()
    if raw not in _BACKEND_REGISTRY:
        return "lemonsqueezy"
    return raw


def get_client(name: str | None = None) -> LicenseClient:
    """Instantiate the named backend. Defaults to the env-var pick.

    Raises ``KeyError`` if the name isn't registered. Tests typically
    don't call this — they pass a ``StubLicenseClient`` instance to
    ``validate_online(client=...)`` directly.
    """
    target = (name or default_backend_name()).lower()
    if target not in _BACKEND_REGISTRY:
        raise KeyError(f"Unknown license backend {target!r}. Known: {sorted(_BACKEND_REGISTRY)}")
    module_path, cls_name = _BACKEND_REGISTRY[target].split(":")
    import importlib

    module = importlib.import_module(module_path)
    return getattr(module, cls_name)()


def supported_backends() -> list[str]:
    """Names of every license backend known to the installer."""
    return list(_BACKEND_REGISTRY.keys())
