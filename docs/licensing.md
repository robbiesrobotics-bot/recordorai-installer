# Licensing — operator runbook

Sprint 5 ships three license-client backends. Pick one based on how
you want to handle payments + license issuance.

## Quick-pick

| Backend | When to use | Setup time | Take |
|---|---|---|---|
| **`lemonsqueezy`** *(default)* | You want to start selling RecordorAI Pro **today**, no infra to host | ~30 min | 5% + Stripe |
| `keygen` | You already have Stripe Billing and want license keys layered on top | ~1 hr | $50/mo + Stripe 2.9% |
| `generic` | You're rolling your own license server (white-label) | ~1-2 days | depends on your stack |

The installer picks the backend at runtime via the
`RECORDORAI_LICENSE_BACKEND` env var. Default is `lemonsqueezy`.

---

## 1. Lemon Squeezy (recommended)

Single service: payments + tax/VAT + license issuance + webhooks. No
server to host.

### One-time setup

1. **Create the LS account** at <https://app.lemonsqueezy.com/>.
2. **Create a Store** (one per brand — "RecordorAI").
3. **Create a Product**: "RecordorAI Pro".
4. **Create a Variant**: "Pro Monthly" — recurring billing, $/month.
5. In the variant's **License Keys** section:
   - Enable license keys.
   - Set "License Key Activation Limit" to whatever per-key
     activation cap you want (e.g. 3 machines per subscription).
   - Set "License Key Expiration" → match the variant's billing
     interval (1 month).
6. Save. Lemon Squeezy now issues a license key to every successful
   subscription. The key is delivered in the post-purchase email and
   surfaced in the buyer's account dashboard.

### What the user sees

- Buys at `recordorai.com/pro` (your LS checkout URL).
- Receives a license-key email (LS's standard template).
- Pastes the key into the installer wizard's Edition screen.
- Wizard validates online → caches the result → unlocks Pro features.
- Subscription auto-renews monthly; if the user cancels, LS marks
  the key inactive on the next billing cycle. The installer's
  periodic re-validation flips the cache to EXPIRED, and Pro
  features lock until they resubscribe.

### What you (operator) do

Nothing recurring. LS handles tax, payment retries, dunning, and
the customer dashboard.

### Configure the installer

```
# Default — no env var needed.
RECORDORAI_LICENSE_BACKEND=lemonsqueezy
```

That's it. The installer calls `api.lemonsqueezy.com` directly.

---

## 2. Keygen.sh

Use when you've already wired up Stripe Billing (or want lower
transaction fees) and want a dedicated license-management layer.

### One-time setup

1. **Create the Keygen account** at <https://keygen.sh/>.
2. **Create a Product**: "RecordorAI Pro".
3. **Create a Policy**: "Pro Monthly" — `floating: true`, `expiration_strategy: "REVOKE_ACCESS"`, `machine_limit: 3` (or whatever).
4. **Wire Stripe**: when a Stripe Checkout session completes for the
   "Pro Monthly" SKU, call Keygen's `POST /v1/accounts/{ACC}/licenses`
   to create a license tied to the Stripe customer. When the
   subscription cancels (Stripe webhook), call Keygen's
   `POST /v1/accounts/{ACC}/licenses/{LIC}/actions/revoke`.
5. Email the issued license key to the customer.

### Configure the installer

```
RECORDORAI_LICENSE_BACKEND=keygen
RECORDORAI_KEYGEN_ACCOUNT=<your account ID>
RECORDORAI_KEYGEN_PRODUCT=<optional product ID — scopes validation>
```

The installer calls `api.keygen.sh` directly. No bearer token needed
for `validate-key` (license keys are unauthenticated, scoped to a
machine fingerprint).

---

## 3. Generic HTTP (self-hosted license server)

For white-label deployments. The installer speaks a small JSON
contract; you implement the server in any language.

### Contract

```
POST $RECORDORAI_LICENSE_URL/v1/licenses/validate
Headers:
    Content-Type: application/json
    Authorization: Bearer $RECORDORAI_LICENSE_TOKEN  (optional)
Body:
    {"license_key": "...", "instance_id": "..." (optional)}
Response (200):
    {
      "valid": true | false,
      "plan": "pro_monthly" | "...",
      "expires_iso": "2026-06-12T00:00:00Z",
      "customer_email": "user@example.com",
      "message": "Subscription active."
    }
```

### Reference FastAPI implementation

```python
# license_server.py
from datetime import datetime, timezone
from fastapi import FastAPI

app = FastAPI()

# In production this comes from your DB.
KEYS = {
    "RAI-PRO-DEMO-1234": {
        "valid": True,
        "plan": "pro_monthly",
        "expires_iso": "2027-01-01T00:00:00Z",
        "customer_email": "demo@yourcompany.com",
    },
}

@app.post("/v1/licenses/validate")
async def validate(body: dict):
    key = body.get("license_key", "")
    record = KEYS.get(key)
    if not record:
        return {"valid": False, "message": "Unknown key"}
    if record["expires_iso"] < datetime.now(timezone.utc).isoformat():
        return {**record, "valid": False, "message": "Expired"}
    return {**record, "message": "Active"}
```

Deploy on Vercel / Railway / Fly.io. Wire your payment processor's
webhooks to populate the KEYS store.

### Configure the installer

```
RECORDORAI_LICENSE_BACKEND=generic
RECORDORAI_LICENSE_URL=https://license.yourcompany.com
RECORDORAI_LICENSE_TOKEN=<optional bearer if your server requires it>
```

---

## How the cache + grace period work

Regardless of backend, the installer caches the last successful
validation in OS-aware data dir:

* macOS: `~/Library/Application Support/RecordorAI Installer/license.json`
* Linux: `~/.local/share/recordorai-installer/license.json`
* Windows: `%LOCALAPPDATA%\RecordorAI\Installer\license.json`

State machine:

```
NEW → ACTIVE  (first valid response)
ACTIVE → GRACE  (offline, ≤7 days since last validate)
GRACE → GRACE_EXPIRED  (offline, >7 days)
ACTIVE → EXPIRED  (server says invalid + plan info present)
ACTIVE → INVALID  (server says invalid + no plan info)
```

Pro features are unlocked in **ACTIVE** and **GRACE**. Everything
else falls back to Community.

The grace window is configurable per-call:

```python
from recordorai_installer.core.license import validate_offline
status = validate_offline(license_key, grace_days=14)
```

7 days is the default — long enough to cover a typical international
trip without locking out a paying customer.

---

## Switching backends mid-flight

Users can switch backends by setting `RECORDORAI_LICENSE_BACKEND`
and re-running the wizard. The cache is backend-agnostic — a key
that's valid on one backend will simply re-validate on the next run
with the new client.

---

## Anti-piracy notes

The installer doesn't ship any DRM. The license check is honor-system
+ activation limit:

* Lemon Squeezy: per-key activation cap (set in the variant's License
  Keys settings). Excess machines fail the activate call.
* Keygen: `machine_limit` in the policy. Excess machines fail
  validate-key.
* Generic: you implement whatever you want.

If you want stronger anti-piracy (signature verification, hardware
binding), look at Keygen's higher-tier "Cryptographically Signed
Licenses" feature — the public key verifies the license offline.
The installer's `KeygenClient` doesn't ship offline verification in
v0.1; opening an issue if you need it.

---

## Testing your back-end before going live

Quickest way to verify the installer is talking to your back-end:

```bash
# Hit the wizard's --rpc surface manually (Sprint 2 added this).
echo '{"jsonrpc":"2.0","id":1,"method":"installer.validate_license","params":{"license_key":"your-test-key"}}' \
  | RECORDORAI_LICENSE_BACKEND=lemonsqueezy recordorai-install --rpc
```

Returns the same JSON the Tauri front-end sees — easiest way to spot
a mis-configured backend.
