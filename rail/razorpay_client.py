"""Thin wrapper over the razorpay SDK: create order, capture, refund, fetch,
payment-signature verification. No ledger import here -- recording what
happened is rail/webhook.py's job, not this module's (writing the record
is not interception, and this module is not the record either).

Orders are seeded outside the agent's action space (see scripts/seed.py):
the agent's action space is capture, refund, payout, all server-side, no
browser. create_order stays here because seed.py needs it too, not because
the agent calls it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import razorpay
from razorpay.errors import BadRequestError, SignatureVerificationError

from rail.config import KEY_ID, KEY_SECRET

_client: Optional[razorpay.Client] = None


def get_client() -> razorpay.Client:
    global _client
    if _client is None:
        _client = razorpay.Client(auth=(KEY_ID, KEY_SECRET))
    return _client


def create_order(amount_paise: int, receipt: str, *, capture: bool = False) -> dict:
    """capture=False (the default) leaves the payment authorized-only --
    manual capture -- which is what every seeded demo order needs, per the
    auto-refund window documented in rail/../.claude/skills/razorpay-testmode."""
    return get_client().order.create(
        {
            "amount": amount_paise,
            "currency": "INR",
            "receipt": receipt,
            "payment_capture": 1 if capture else 0,
        }
    )


@dataclass(frozen=True)
class CaptureResult:
    success: bool
    payment: Optional[dict] = None
    error: Optional[str] = None


def attempt_capture(payment_id: str, amount_paise: int) -> CaptureResult:
    """Capture is real agent action space: a Razorpay-side rejection
    (already captured, past manual_expiry_period, amount mismatch) is an
    expected outcome to report, not a crash to propagate."""
    try:
        payment = get_client().payment.capture(payment_id, amount_paise)
        return CaptureResult(success=True, payment=payment)
    except BadRequestError as e:
        return CaptureResult(success=False, error=str(e))


def refund(payment_id: str, amount_paise: int) -> dict:
    """Two-argument form only: client.payment.refund(payment_id, {"amount":
    N}). razorpay/resources/payment.py (v2.0.1) defines Payment.refund
    twice -- refund(self, payment_id, amount, data={}) at line 52, then
    refund(self, payment_id, data={}) at line 120. Class-body assignment
    means the second silently wins; the first is dead code, never called.
    Calling the old three-arg shape (payment_id, amount_int) binds that int
    positionally to `data`, so post_url ships a bare int as the request
    body instead of {"amount": ...}. Confirmed against test mode with the
    correct two-arg form; the old shape was never exercised, on purpose."""
    return get_client().payment.refund(payment_id, {"amount": amount_paise})


def fetch_payment(payment_id: str) -> dict:
    return get_client().payment.fetch(payment_id)


def verify_payment_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """Checkout's client-side handler response is untrusted until this
    passes. Authentication only, not fulfilment -- fulfil on the webhook."""
    try:
        return get_client().utility.verify_payment_signature(
            {
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": signature,
            }
        )
    except SignatureVerificationError:
        return False
