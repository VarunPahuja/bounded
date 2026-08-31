"""Phase 3 Part A spec (MASTER.md, CLAUDE.md canonical-serialization decision).

No network, no policy import -- pure Python arithmetic over frozen
contracts.models.LedgerEntry, per the scope boundary in CLAUDE.md.
"""

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from contracts.models import LedgerDecision, LedgerEntry
from ledger.chain import (
    FIELD_ORDER,
    GENESIS_PREV_HASH,
    append_entry,
    canonical_timestamp,
    compute_entry_hash,
    verify_chain,
)
from tests.ledger._helpers import build_chain, ts


def test_chain_verifies():
    private_key = Ed25519PrivateKey.generate()
    entries = build_chain(50, private_key)
    assert verify_chain(entries, private_key.public_key()) is None


def test_chain_detects_tampering():
    private_key = Ed25519PrivateKey.generate()
    entries = build_chain(50, private_key)
    tampered = deepcopy(entries)
    victim = tampered[17]
    assert victim.action is not None
    tampered[17] = victim.model_copy(
        update={"action": victim.action.model_copy(update={"amount_paise": victim.action.amount_paise + 1})}
    )
    broken_at = verify_chain(tampered, private_key.public_key())
    assert broken_at == 17


def test_chain_detects_deletion():
    private_key = Ed25519PrivateKey.generate()
    entries = build_chain(50, private_key)
    with_deletion = entries[:20] + entries[21:]
    broken_at = verify_chain(with_deletion, private_key.public_key())
    assert broken_at == 20


def test_signature_detects_forgery():
    signer_key = Ed25519PrivateKey.generate()
    attacker_key = Ed25519PrivateKey.generate()
    entries = build_chain(10, signer_key)
    # A clean hash chain, verified against the wrong public key: hashes still
    # recompute correctly (nobody edited the payload), but no signature in
    # the chain was made by attacker_key's private half.
    broken_at = verify_chain(entries, attacker_key.public_key())
    assert broken_at == 0


def test_canonical_form_is_stable():
    timestamp = ts()
    entry_a = append_entry(
        None,
        entry_id="e0",
        timestamp=timestamp,
        decision=LedgerDecision.GENESIS,
        private_key=Ed25519PrivateKey.generate(),
    )
    # Independently construct an equal-valued entry via a different code
    # path (dict-unpacking into the model rather than keyword args) and
    # confirm the hash function is a pure function of field values, not of
    # construction history.
    fields = dict(
        index=0,
        entry_id="e0",
        timestamp=timestamp,
        decision=LedgerDecision.GENESIS,
        action=None,
        verification_result=None,
        razorpay_payment_id=None,
        prev_hash=GENESIS_PREV_HASH,
        entry_hash="",
        signature="",
    )
    entry_b_draft = LedgerEntry(**fields)
    assert compute_entry_hash(entry_a) == compute_entry_hash(entry_b_draft)


def test_timestamp_is_timezone_normalized():
    utc_dt = datetime(2026, 8, 30, 12, 0, 0, 123_456, tzinfo=timezone.utc)
    ist_dt = utc_dt.astimezone(timezone(timedelta(hours=5, minutes=30)))
    assert canonical_timestamp(utc_dt) == canonical_timestamp(ist_dt)
    assert canonical_timestamp(utc_dt) == "2026-08-30T12:00:00.123456Z"

    naive_dt = datetime(2026, 8, 30, 12, 0, 0, 123_456)
    with pytest.raises(ValueError):
        canonical_timestamp(naive_dt)


def test_field_order_is_pinned():
    assert FIELD_ORDER == (
        "index",
        "entry_id",
        "timestamp",
        "decision",
        "action",
        "verification_result",
        "razorpay_payment_id",
        "prev_hash",
    )


def test_known_entry_hashes_to_known_value():
    entry = LedgerEntry(
        index=0,
        entry_id="golden-entry",
        timestamp=datetime(2026, 1, 1, 0, 0, 0, 0, tzinfo=timezone.utc),
        decision=LedgerDecision.GENESIS,
        action=None,
        verification_result=None,
        razorpay_payment_id=None,
        prev_hash=GENESIS_PREV_HASH,
        entry_hash="",
        signature="",
    )
    # Generated once from compute_entry_hash and committed here. A future
    # failure of this test is a question about what changed in the
    # canonical form (Pydantic upgrade, field-order edit, etc.), never a
    # value to casually update.
    assert (
        compute_entry_hash(entry)
        == "03cf6cd1c750bb98888d93c7be18dd9c186f788932e97fc0559e90a5f840d72e"
    )
