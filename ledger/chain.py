"""Hash-chained, Ed25519-signed audit ledger over `contracts.models.LedgerEntry`.

No network, no policy, no verifier import. Pure Python arithmetic over frozen
types. Scope boundary per CLAUDE.md: this module is not on the enforcement
path, it is the record of what the enforcement path decided.

CANONICAL SERIALIZATION -- read this before touching the hash function.

Two processes hashing the same LedgerEntry must produce identical bytes,
forever, regardless of Python/Pydantic version. That guarantee rests on four
decisions, all made explicitly in code rather than inherited from a library
default:

1. FIELD ORDER is a hand-written tuple (FIELD_ORDER below), not Pydantic's
   model field order. `entry_hash` and `signature` are never inputs to the
   hash: `entry_hash` cannot commit to itself, and `signature` is computed
   over `entry_hash`, not alongside it. Fields are joined with a 0x1F unit
   separator so `entry_id="ab"` + `decision="c"` cannot collide with
   `entry_id="a"` + `decision="bc"`.

2. TIMESTAMPS are UTC, microsecond precision, formatted by
   `canonical_timestamp()` as "%Y-%m-%dT%H:%M:%S.%fZ" -- never a library's
   default datetime-to-JSON conversion, which can shift across versions.
   A naive datetime (no tzinfo) RAISES. It is never silently treated as UTC
   or as local time -- a caller that forgot tzinfo gets a loud failure, not
   a hash that looks plausible and is wrong. A non-UTC aware datetime is
   converted to UTC before formatting, so the same instant always produces
   the same bytes regardless of the offset it arrived in.

   Storage note (ledger/store.py): the canonical timestamp STRING is what
   gets persisted, in a String/TEXT column, never a native SQLite DATETIME
   column. That sidesteps SQLite/SQLAlchemy datetime-adapter round-trip
   quirks entirely -- there is no adapter in the path to lose precision,
   because verification always hashes the exact string that was stored.

3. MONEY IS INTEGER, always. Paise amounts and `index`: plain Python `int`,
   rendered by `json.dumps` as bare digits, never `Decimal`. This is
   enforced upstream, not here -- `Action.amount_paise` is a frozen
   Pydantic `int` field, validated before an `Action` ever reaches this
   module. This module does not re-litigate that: `VerificationResult`
   legitimately carries a non-money `float` (`latency_ms`), and Python's
   float JSON serialization is deterministic (shortest round-trip repr,
   specified by the language, not the platform), so floats are canonicalized
   as-is. What is banned is a money field silently becoming a float --
   that boundary is the frozen contract's job, not this function's.

4. NONE is always an explicit JSON `null`, never an omitted key and never
   `""`. Optional fields (`action`, `verification_result`,
   `razorpay_payment_id`, and everything Optional nested inside them)
   serialize their absence identically every time.

Nested objects (`Action`, `VerificationResult` -> `Counterexample` ->
`list[CounterexampleStep]`) are walked by `canonicalize()` below: Pydantic
models become dicts via `model_dump(mode="python")` (kept as Python objects,
not pre-serialized to JSON-ish strings by Pydantic itself), enums become
their `.value`, then the whole structure is re-walked so nothing library-
controlled reaches `json.dumps` un-inspected. The final JSON text uses
`sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False`.

SIGNING: Ed25519 over the UTF-8 bytes of the hex `entry_hash` string, not
over the raw digest and not over the full canonical payload. Verifying a
signature only ever needs `entry_hash`; forging either the payload or the
hash without the private key still fails signature verification, because
`entry_hash` is itself a function of the canonical payload. A hash chain
alone proves nobody edited a record in place. The signature is what proves
who wrote it.

GENESIS gets no special-cased hash function -- only its `prev_hash` is a
constant (64 hex zeros). It is signed exactly like every other entry.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from pydantic import BaseModel

from contracts.models import Action, LedgerDecision, LedgerEntry, VerificationResult

GENESIS_PREV_HASH = "0" * 64

SEP = b"\x1f"

# Hand-written, not derived from LedgerEntry's field order. This is what
# keeps old hashes valid if contracts/models.py ever reorders its fields --
# pinned by test_field_order_is_pinned.
FIELD_ORDER: tuple[str, ...] = (
    "index",
    "entry_id",
    "timestamp",
    "decision",
    "action",
    "verification_result",
    "razorpay_payment_id",
    "prev_hash",
)


def canonical_timestamp(dt: datetime) -> str:
    """UTC, microsecond precision, fixed string form. Naive datetimes raise."""
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(
            "canonical_timestamp requires a timezone-aware datetime; "
            "naive datetimes are never silently assumed to be UTC"
        )
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def canonicalize(value: object) -> object:
    """Recursively reduce a value to JSON-safe primitives we fully control.

    Order of isinstance checks matters: Enum before BaseModel/str (several
    enums in contracts.models subclass str), bool before int (bool is an
    int subclass in Python).
    """
    if value is None:
        return None
    if isinstance(value, Enum):
        return canonicalize(value.value)
    if isinstance(value, BaseModel):
        return canonicalize(value.model_dump(mode="python"))
    if isinstance(value, dict):
        return {k: canonicalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [canonicalize(v) for v in value]
    if isinstance(value, datetime):
        return canonical_timestamp(value)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, str)):
        return value
    raise TypeError(f"cannot canonicalize value of type {type(value)!r}")


def canonical_json_bytes(value: object) -> bytes:
    if value is None:
        return b"null"
    return json.dumps(
        canonicalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def compute_entry_hash(entry: LedgerEntry) -> str:
    """SHA256(canonical_fields || prev_hash), per FIELD_ORDER. Excludes
    entry_hash and signature -- neither can be an input to this function."""
    parts: list[bytes] = []
    for field in FIELD_ORDER:
        if field == "index":
            parts.append(str(entry.index).encode("utf-8"))
        elif field == "entry_id":
            parts.append(entry.entry_id.encode("utf-8"))
        elif field == "timestamp":
            parts.append(canonical_timestamp(entry.timestamp).encode("utf-8"))
        elif field == "decision":
            parts.append(entry.decision.value.encode("utf-8"))
        elif field == "action":
            parts.append(canonical_json_bytes(entry.action))
        elif field == "verification_result":
            parts.append(canonical_json_bytes(entry.verification_result))
        elif field == "razorpay_payment_id":
            parts.append(
                b"null"
                if entry.razorpay_payment_id is None
                else entry.razorpay_payment_id.encode("utf-8")
            )
        elif field == "prev_hash":
            parts.append(entry.prev_hash.encode("utf-8"))
        else:  # pragma: no cover -- guarded by test_field_order_is_pinned
            raise AssertionError(f"unhandled field in FIELD_ORDER: {field}")
    return hashlib.sha256(SEP.join(parts)).hexdigest()


def sign_entry_hash(entry_hash: str, private_key: Ed25519PrivateKey) -> str:
    return private_key.sign(entry_hash.encode("utf-8")).hex()


def verify_entry_signature(
    entry_hash: str, signature_hex: str, public_key: Ed25519PublicKey
) -> bool:
    try:
        public_key.verify(bytes.fromhex(signature_hex), entry_hash.encode("utf-8"))
        return True
    except (InvalidSignature, ValueError):
        return False


def append_entry(
    prev: Optional[LedgerEntry],
    *,
    entry_id: str,
    timestamp: datetime,
    decision: LedgerDecision,
    private_key: Ed25519PrivateKey,
    action: Optional[Action] = None,
    verification_result: Optional[VerificationResult] = None,
    razorpay_payment_id: Optional[str] = None,
) -> LedgerEntry:
    """Build the next entry in the chain. prev=None builds genesis (index 0,
    prev_hash=GENESIS_PREV_HASH). No other branch of this function is
    genesis-specific -- the hash and signature are computed identically."""
    index = 0 if prev is None else prev.index + 1
    prev_hash = GENESIS_PREV_HASH if prev is None else prev.entry_hash

    draft = LedgerEntry(
        index=index,
        entry_id=entry_id,
        timestamp=timestamp,
        decision=decision,
        action=action,
        verification_result=verification_result,
        razorpay_payment_id=razorpay_payment_id,
        prev_hash=prev_hash,
        entry_hash="",
        signature="",
    )
    entry_hash = compute_entry_hash(draft)
    signature = sign_entry_hash(entry_hash, private_key)
    return draft.model_copy(update={"entry_hash": entry_hash, "signature": signature})


def verify_chain(
    entries: list[LedgerEntry], public_key: Ed25519PublicKey
) -> Optional[int]:
    """Walk the chain from genesis. Returns the first index where it breaks
    (bad index, broken prev_hash link, hash mismatch, or bad signature), or
    None if the whole chain verifies clean."""
    expected_prev_hash = GENESIS_PREV_HASH
    for i, entry in enumerate(entries):
        if entry.index != i:
            return i
        if entry.prev_hash != expected_prev_hash:
            return i
        if compute_entry_hash(entry) != entry.entry_hash:
            return i
        if not verify_entry_signature(entry.entry_hash, entry.signature, public_key):
            return i
        expected_prev_hash = entry.entry_hash
    return None
