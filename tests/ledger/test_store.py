"""SQLite persistence layer for the hash chain. No network, no policy import."""

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from contracts.models import LedgerDecision
from ledger.chain import GENESIS_PREV_HASH, append_entry, verify_chain
from ledger.store import append, get_tip, ledger_entries, load_all, make_engine
from tests.ledger._helpers import build_chain, ts


def test_store_round_trip_preserves_chain():
    private_key = Ed25519PrivateKey.generate()
    entries = build_chain(20, private_key)
    engine = make_engine()
    for entry in entries:
        append(engine, entry)

    loaded = load_all(engine)
    assert loaded == entries
    assert verify_chain(loaded, private_key.public_key()) is None


def test_store_get_tip_empty_is_none():
    engine = make_engine()
    assert get_tip(engine) is None


def test_store_get_tip_matches_last_append():
    private_key = Ed25519PrivateKey.generate()
    entries = build_chain(5, private_key)
    engine = make_engine()
    for entry in entries:
        append(engine, entry)
    assert get_tip(engine) == entries[-1]


def test_store_rejects_out_of_order_index():
    private_key = Ed25519PrivateKey.generate()
    engine = make_engine()
    genesis = append_entry(
        None,
        entry_id="e0",
        timestamp=ts(),
        decision=LedgerDecision.GENESIS,
        private_key=private_key,
    )
    append(engine, genesis)

    # Skips index 1 -- built as if genesis were its own prev, forging index 2.
    bad = append_entry(
        genesis,
        entry_id="e2",
        timestamp=ts(2),
        decision=LedgerDecision.ALLOW,
        private_key=private_key,
    ).model_copy(update={"index": 2})

    with pytest.raises(ValueError):
        append(engine, bad)


def test_store_rejects_prev_hash_mismatch():
    private_key = Ed25519PrivateKey.generate()
    engine = make_engine()
    genesis = append_entry(
        None,
        entry_id="e0",
        timestamp=ts(),
        decision=LedgerDecision.GENESIS,
        private_key=private_key,
    )
    append(engine, genesis)

    forged = append_entry(
        None,
        entry_id="e1",
        timestamp=ts(1),
        decision=LedgerDecision.ALLOW,
        private_key=private_key,
    )  # built with prev=None, so prev_hash=GENESIS_PREV_HASH, wrong for slot 1

    with pytest.raises(ValueError):
        append(engine, forged)


def test_store_rejects_self_inconsistent_entry_hash():
    private_key = Ed25519PrivateKey.generate()
    engine = make_engine()
    genesis = append_entry(
        None,
        entry_id="e0",
        timestamp=ts(),
        decision=LedgerDecision.GENESIS,
        private_key=private_key,
    )
    tampered = genesis.model_copy(update={"entry_id": "tampered-but-hash-unchanged"})

    with pytest.raises(ValueError):
        append(engine, tampered)


def test_store_append_only_rejects_raw_update():
    private_key = Ed25519PrivateKey.generate()
    engine = make_engine()
    append(
        engine,
        append_entry(
            None,
            entry_id="e0",
            timestamp=ts(),
            decision=LedgerDecision.GENESIS,
            private_key=private_key,
        ),
    )
    with engine.begin() as conn, pytest.raises(Exception):
        conn.execute(
            ledger_entries.update()
            .where(ledger_entries.c.idx == 0)
            .values(entry_id="hacked")
        )


def test_store_append_only_rejects_raw_delete():
    private_key = Ed25519PrivateKey.generate()
    engine = make_engine()
    append(
        engine,
        append_entry(
            None,
            entry_id="e0",
            timestamp=ts(),
            decision=LedgerDecision.GENESIS,
            private_key=private_key,
        ),
    )
    with engine.begin() as conn, pytest.raises(Exception):
        conn.execute(ledger_entries.delete().where(ledger_entries.c.idx == 0))
