---
name: razorpay-testmode
description: Razorpay test-mode integration: orders, paise amounts, payment and webhook signature verification, idempotency, and an offline stub gateway. Use whenever Razorpay or payment webhooks come up.
---

# Razorpay in test mode

Test mode is a fully separate environment: separate keys, separate dashboard data, separate webhooks, separate webhook secret. No real money moves and only designated test credentials are accepted, because test mode never talks to banking networks at all. Nothing crosses over. That separation is the feature, so the first rule is to make the mode impossible to get wrong in code, not just in configuration.

## Guardrails first

```python
# app/payments/config.py
import os

KEY_ID = os.environ["RAZORPAY_KEY_ID"]
KEY_SECRET = os.environ["RAZORPAY_KEY_SECRET"]
WEBHOOK_SECRET = os.environ["RAZORPAY_WEBHOOK_SECRET"]
ALLOW_LIVE = os.getenv("RAZORPAY_ALLOW_LIVE", "false").lower() == "true"

if not KEY_ID.startswith("rzp_test_") and not ALLOW_LIVE:
    raise RuntimeError(
        f"Refusing to boot with non-test Razorpay key {KEY_ID[:12]}... "
        "Set RAZORPAY_ALLOW_LIVE=true only in production."
    )
```

Fail at import, not at first charge. A live key in a dev container is a bad afternoon.

Also: keys in `.env` and `.env` in `.gitignore`, key secret never sent to the browser (only `key_id` goes to checkout), webhook secret is a value you choose in the dashboard and is **not** your API secret.

## Money is an integer

Amounts are in paise. Rs 500 is `50000`. Never let a float touch this.

```python
from decimal import Decimal, ROUND_HALF_UP

def to_paise(rupees: str | Decimal) -> int:
    return int((Decimal(rupees) * 100).quantize(Decimal("1"), ROUND_HALF_UP))
```

Store paise in the DB as `BIGINT`. Format to rupees only at the view layer. Every rounding bug in a payments codebase starts with someone storing `499.99` as a float.

## The three flows

### 1. Create an order (server side)

```python
import razorpay
client = razorpay.Client(auth=(KEY_ID, KEY_SECRET))

order = client.order.create({
    "amount": to_paise("500.00"),
    "currency": "INR",
    "receipt": f"inv_{invoice_id}",          # your id, max 40 chars
    "notes": {"invoice_id": str(invoice_id)}, # comes back on the webhook
    "payment_capture": 1,
})
```

Persist `order["id"]` against your invoice **before** returning it to the client. If you do not, a webhook can arrive for an order you have no record of.

`notes` is the join key back to your domain. Use it. Parsing `receipt` strings later is worse.

### 2. Verify the payment signature (server side, after checkout)

Checkout returns `razorpay_order_id`, `razorpay_payment_id`, `razorpay_signature` to your frontend. The frontend cannot be trusted, so verify server side. The signature is HMAC-SHA256 of `order_id|payment_id` keyed with your **API key secret**.

```python
import hmac, hashlib

def verify_payment(order_id: str, payment_id: str, signature: str) -> bool:
    expected = hmac.new(
        KEY_SECRET.encode(),
        f"{order_id}|{payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

`compare_digest`, not `==`. And treat this as authentication only, not as fulfilment. Fulfil on the webhook.

### 3. Webhook (the actual source of truth)

Each webhook carries an `X-Razorpay-Signature` header: a hex HMAC-SHA256 over the raw request body, keyed with the dashboard webhook secret, which is separate from your API key. Razorpay is explicit that the body passed to the signature check must be the raw request body, not parsed or cast.

```python
# app/api/webhooks.py
import hmac, hashlib, json
from fastapi import APIRouter, Request, Header, HTTPException

router = APIRouter()

@router.post("/webhooks/razorpay")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(...),
    x_razorpay_event_id: str = Header(...),
):
    raw = await request.body()                      # bytes, before any parsing
    expected = hmac.new(WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, x_razorpay_signature):
        raise HTTPException(400, "bad signature")

    if await already_processed(x_razorpay_event_id):
        return {"ok": True, "duplicate": True}

    event = json.loads(raw)
    if event["event"] == "payment.captured":
        entity = event["payload"]["payment"]["entity"]
        await settle(invoice_id=entity["notes"]["invoice_id"],
                     payment_id=entity["id"],
                     amount_paise=entity["amount"])

    await mark_processed(x_razorpay_event_id)
    return {"ok": True}
```

Two things carry the weight here:

- **Raw body.** If you read `await request.json()` and re-serialise, key order and whitespace change and the HMAC will never match. This is the single most common Razorpay integration bug.
- **Idempotency.** Duplicate deliveries are expected behaviour, and the `x-razorpay-event-id` header is unique per event so you can identify repeats. Store processed event ids in a table with a unique index and let the insert conflict be your lock. Ordering is best effort too, so never assume `order.paid` arrives before `payment.captured`.

Return 2xx fast. Do the slow work in a background task. A timeout gets you retried.

## Testing without a browser

**Simulating outcomes.** Test mode shows a mock bank page with Success and Failure buttons, so you drive the outcome yourself rather than needing a specific declining card. On UPI, `success@razorpay` completes and `failure@razorpay` fails. Card numbers rotate, so pull the current list from Razorpay's test card docs at integration time rather than hardcoding a list from a blog post.

One trap worth knowing: in test mode, cancelling a UPI payment resolves as a success, so cancellation flows cannot be tested there. If cancel handling matters, cover it with a synthetic webhook instead.

**Local webhooks.** Razorpay only POSTs to a public URL. Use a tunnel (`ngrok http 8000`) and register the tunnel URL in the test mode dashboard under Settings > Webhooks. Re-register when the tunnel restarts, or pay for a fixed subdomain.

**Unit tests need no network.** Sign a fixture body yourself:

```python
def signed(body: dict, secret: str = "whsec_test"):
    raw = json.dumps(body, separators=(",", ":")).encode()
    sig = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return raw, sig

def test_rejects_tampered_body(client):
    raw, sig = signed({"event": "payment.captured", "payload": {...}})
    tampered = raw.replace(b'"amount":50000', b'"amount":500000')
    r = client.post("/webhooks/razorpay", content=tampered,
                    headers={"X-Razorpay-Signature": sig,
                             "X-Razorpay-Event-Id": "evt_1"})
    assert r.status_code == 400
```

Test at minimum: valid signature accepted, tampered body rejected, missing header rejected, same event id twice settles once, unknown event type ignored without a 500.

## Stub adapter

Do not let a demo depend on a tunnel, a dashboard session, or wifi. Put one interface in front of the gateway and pick the implementation by env var.

```python
# app/payments/gateway.py
from typing import Protocol

class PaymentGateway(Protocol):
    def create_order(self, amount_paise: int, ref: str) -> dict: ...
    def refund(self, payment_id: str, amount_paise: int) -> dict: ...

class StubGateway:
    """Deterministic. No network. Default in CI and in demos."""
    def __init__(self): self._n = 0
    def create_order(self, amount_paise, ref):
        self._n += 1
        return {"id": f"order_STUB{self._n:06d}", "amount": amount_paise,
                "status": "created", "receipt": ref}
    def refund(self, payment_id, amount_paise):
        return {"id": f"rfnd_STUB{payment_id[-6:]}", "status": "processed"}

def get_gateway() -> PaymentGateway:
    mode = os.getenv("PAYMENTS_MODE", "stub")   # stub | test | live
    return {"stub": StubGateway, "test": RazorpayGateway,
            "live": RazorpayGateway}[mode]()
```

`stub` is the default. You opt into the network, you never fall into it. This also means your test suite has no flaky gateway dependency and your demo runs on a train.

## Refunds and other test mode differences

- Refunds in test mode resolve instantly. In live they are asynchronous, so build the async path (`refund.processed` webhook) even though test mode never exercises the waiting state.
- There are no settlements in test mode. Any reconciliation logic against settlement reports needs fixtures.
- Test and live have independent webhook registrations and independent secrets. Copying a working live config into test is a common cause of "signature always fails".

## Checklist before you call it done

- [ ] Boot guard rejects non-`rzp_test_` keys unless explicitly allowed
- [ ] Key secret never leaves the server; only `key_id` reaches the browser
- [ ] Amounts are integers in paise end to end
- [ ] Order id persisted before checkout opens
- [ ] Payment signature verified server side with `compare_digest`
- [ ] Webhook verified over the raw body, before parsing
- [ ] Event ids deduplicated with a unique index
- [ ] Handler returns 2xx quickly, work happens async
- [ ] `PAYMENTS_MODE=stub` is the default and CI never hits the network
- [ ] Amount and currency on the webhook are checked against the stored invoice, not trusted
