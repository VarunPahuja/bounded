"""No network. Signs fixture bodies itself, per razorpay-testmode skill's
'unit tests need no network' guidance -- webhook verification is pure HMAC
over bytes, it does not need Razorpay to prove it works."""

import hashlib
import hmac
import json
import threading
from datetime import datetime, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from contracts.models import LedgerDecision
from ledger.chain import append_entry
from ledger.store import append as ledger_append, load_all, make_engine
from rail.webhook import process_webhook_event, verify_webhook_signature

SECRET = "whsec_test"


def signed_body(event: dict, secret: str = SECRET) -> tuple[bytes, str]:
    raw = json.dumps(event, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return raw, sig


def sample_event(payment_id: str = "pay_1") -> dict:
    return {
        "event": "payment.captured",
        "payload": {"payment": {"entity": {"id": payment_id, "amount": 100}}},
    }


def seeded_engine(private_key: Ed25519PrivateKey):
    engine = make_engine()
    genesis = append_entry(
        None,
        entry_id="genesis",
        timestamp=datetime.now(timezone.utc),
        decision=LedgerDecision.GENESIS,
        private_key=private_key,
    )
    ledger_append(engine, genesis)
    return engine


def test_verify_webhook_signature_accepts_valid():
    raw, sig = signed_body(sample_event())
    assert verify_webhook_signature(raw, sig, SECRET) is True


def test_verify_webhook_signature_rejects_tampered_body():
    raw, sig = signed_body(sample_event())
    tampered = raw.replace(b'"amount":100', b'"amount":100000')
    assert verify_webhook_signature(tampered, sig, SECRET) is False


def test_verify_webhook_signature_rejects_wrong_secret():
    raw, sig = signed_body(sample_event())
    assert verify_webhook_signature(raw, sig, "whsec_other") is False


def test_process_webhook_event_rejects_bad_signature():
    private_key = Ed25519PrivateKey.generate()
    engine = seeded_engine(private_key)
    raw, sig = signed_body(sample_event())

    result = process_webhook_event(
        raw, "0" * 64, "evt_1", SECRET, engine, private_key
    )

    assert result is None
    assert len(load_all(engine)) == 1  # only genesis


def test_process_webhook_event_appends_one_entry():
    private_key = Ed25519PrivateKey.generate()
    engine = seeded_engine(private_key)
    raw, sig = signed_body(sample_event("pay_appended"))

    result = process_webhook_event(raw, sig, "evt_1", SECRET, engine, private_key)

    assert result is not None
    entries = load_all(engine)
    assert len(entries) == 2
    assert entries[-1].entry_id == "evt_1"
    assert entries[-1].razorpay_payment_id == "pay_appended"
    assert entries[-1].decision == LedgerDecision.ALLOW


def test_webhook_idempotent():
    private_key = Ed25519PrivateKey.generate()
    engine = seeded_engine(private_key)
    raw, sig = signed_body(sample_event("pay_dup"))

    first = process_webhook_event(raw, sig, "evt_dup", SECRET, engine, private_key)
    second = process_webhook_event(raw, sig, "evt_dup", SECRET, engine, private_key)

    assert first is not None
    assert second is None
    assert len(load_all(engine)) == 2  # genesis + one recorded event


def test_webhook_concurrent_duplicate():
    """Two process_webhook_event calls, same event_id, launched to race each
    other. Exactly one ledger entry for it must survive -- this is the case
    a check-then-append (existence check, then append) cannot guarantee,
    only the UNIQUE constraint on entry_id can."""
    private_key = Ed25519PrivateKey.generate()
    engine = seeded_engine(private_key)
    raw, sig = signed_body(sample_event("pay_race"))

    results: list = []
    barrier = threading.Barrier(2)

    def worker():
        barrier.wait()
        results.append(
            process_webhook_event(raw, sig, "evt_race", SECRET, engine, private_key)
        )

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    successes = [r for r in results if r is not None]
    assert len(successes) == 1

    entries = load_all(engine)
    race_entries = [e for e in entries if e.entry_id == "evt_race"]
    assert len(race_entries) == 1
