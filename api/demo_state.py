"""Shared demo-backend state for the Phase 7 dashboard API (docs/PHASE7-PLAN.md):
the Ed25519 signing key and the persistent SQLite ledger the Ledger surface
reads. Pure infrastructure, not a new decision path -- every verdict still
comes from verifier/bmc.py via rail/interceptor.py, unchanged.

The signing key is loaded from disk (generated once) so the persistent
ledger's signatures stay verifiable across dashboard restarts. The Attacks
surface deliberately does NOT use the persistent ledger -- each scenario run
gets its own fresh, isolated in-memory chain (fresh_isolated_engine) so
re-running, or running two different scenarios back to back, can never
contaminate one another's accumulated state.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from sqlalchemy.engine import Engine

from contracts.models import LedgerDecision
from ledger.chain import append_entry
from ledger.store import append as ledger_append, get_tip, make_engine

_API_DIR = Path(__file__).resolve().parent
DEMO_DB_PATH = _API_DIR / "demo_ledger.db"
DEMO_KEY_PATH = _API_DIR / "demo_key.pem"


def _load_or_create_private_key() -> Ed25519PrivateKey:
    if DEMO_KEY_PATH.exists():
        loaded = serialization.load_pem_private_key(DEMO_KEY_PATH.read_bytes(), password=None)
        assert isinstance(loaded, Ed25519PrivateKey)
        return loaded
    key = Ed25519PrivateKey.generate()
    DEMO_KEY_PATH.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    return key


_PRIVATE_KEY = _load_or_create_private_key()


def demo_private_key() -> Ed25519PrivateKey:
    return _PRIVATE_KEY


def demo_public_key() -> Ed25519PublicKey:
    return _PRIVATE_KEY.public_key()


def _genesis_entry():
    return append_entry(
        None,
        entry_id="genesis",
        timestamp=datetime.now(timezone.utc),
        decision=LedgerDecision.GENESIS,
        private_key=_PRIVATE_KEY,
    )


def demo_engine() -> Engine:
    """The persistent ledger the Ledger surface reads. Created once on first
    call; genesis appended only if the file is empty.
    """
    engine = make_engine(str(DEMO_DB_PATH))
    if get_tip(engine) is None:
        ledger_append(engine, _genesis_entry())
    return engine


def fresh_isolated_engine() -> Engine:
    """A brand-new in-memory ledger + genesis entry, scoped to one Attacks-
    surface scenario run."""
    engine = make_engine(":memory:")
    ledger_append(engine, _genesis_entry())
    return engine
