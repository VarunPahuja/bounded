"""Webhook signature verification and idempotent recording. Writing the
ledger record here is not interception -- Phase 4's interceptor gates a
proposed action before it reaches Razorpay; this only records an event
Razorpay has already delivered, after Razorpay already executed it.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy.engine import Engine

from contracts.models import LedgerDecision
from ledger.chain import append_entry
from ledger.store import DuplicateEntryError, append as ledger_append, get_tip

_MAX_APPEND_ATTEMPTS = 5


def verify_webhook_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    """raw_body must be the exact bytes Razorpay sent -- re-serializing
    parsed JSON changes key order and whitespace, which silently breaks the
    HMAC. Typing this parameter bytes, not dict, is what stops that mistake
    at the call site rather than relying on a comment to."""
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _extract_payment_id(event: dict) -> Optional[str]:
    payment = event.get("payload", {}).get("payment", {}).get("entity", {})
    return payment.get("id")


def process_webhook_event(
    raw_body: bytes,
    signature: str,
    event_id: str,
    secret: str,
    engine: Engine,
    private_key: Ed25519PrivateKey,
) -> Optional[dict]:
    """Verify, then append exactly one ledger entry keyed by event_id.

    Returns the parsed event dict on a fresh append, None on a rejected
    signature or an already-processed duplicate. Callers return 2xx to
    Razorpay either way -- Razorpay's retry contract expects that, and a
    duplicate is not an error.

    Idempotency is enforced by the UNIQUE constraint on entry_id
    (ledger/store.py), not by a check-then-append: two concurrent calls for
    the same event_id can both read the same tip before either commits.
    ledger.store.append() re-validates the chain position under its own
    lock, so a losing entry is rejected with a plain ValueError (wrong
    slot, not yet a duplicate) -- this loop retries against the fresh tip,
    which either succeeds as a genuinely new entry or resolves the race as
    a DuplicateEntryError once it lands on the same entry_id.
    """
    if not verify_webhook_signature(raw_body, signature, secret):
        return None

    event = json.loads(raw_body)
    payment_id = _extract_payment_id(event)

    for _ in range(_MAX_APPEND_ATTEMPTS):
        tip = get_tip(engine)
        entry = append_entry(
            tip,
            entry_id=event_id,
            timestamp=datetime.now(timezone.utc),
            decision=LedgerDecision.ALLOW,
            private_key=private_key,
            razorpay_payment_id=payment_id,
        )
        try:
            ledger_append(engine, entry)
            return event
        except DuplicateEntryError:
            return None
        except ValueError:
            continue  # lost the race for this chain slot; retry on the new tip

    raise RuntimeError(
        f"process_webhook_event: could not append entry for {event_id!r} "
        f"after {_MAX_APPEND_ATTEMPTS} attempts (sustained chain contention)"
    )
