"""SQLite persistence for the hash chain in ledger/chain.py. One schema, no
Alembic, per MASTER.md ("SQLite via SQLAlchemy for dev... no migrations").

Each row's `payload` column is the full `LedgerEntry.model_dump_json()` --
one Pydantic-owned serialization, used only for storage/reload fidelity.
It is a DIFFERENT serialization from ledger.chain's canonical form: the
canonical form exists to be hashed identically across processes, this one
exists to round-trip a Python object through SQLite without loss. They are
never conflated. In particular the entry's `timestamp` field is embedded as
a string *inside* this JSON text -- it never touches a native SQLite
DATETIME column or SQLAlchemy's datetime adapter, so there is no adapter in
the path that could silently reformat or truncate it. `idx`, `entry_hash`,
and `prev_hash` are pulled out as their own indexed columns purely for
query convenience; the payload column is the single source of truth on
reload, per every field.

Append-only is enforced twice: SQLite triggers reject UPDATE/DELETE at the
DB level (defeatable by anyone who can ALTER TABLE ... DISABLE TRIGGER --
that is what the hash chain and its signatures are for), and `append()`
refuses, before ever touching the DB, to write an entry whose `index`/
`prev_hash` do not chain from the current tip, or whose `entry_hash` does
not match what ledger.chain recomputes from its own fields. Fail closed:
a structurally bad entry is a ValueError, never a silently accepted row.
"""

from __future__ import annotations

import threading
from typing import Optional

from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    event,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

from contracts.models import LedgerEntry
from ledger.chain import GENESIS_PREV_HASH, compute_entry_hash

metadata = MetaData()

ledger_entries = Table(
    "ledger_entries",
    metadata,
    Column("idx", Integer, primary_key=True, autoincrement=False),
    Column("entry_id", String, nullable=False, unique=True),
    Column("entry_hash", String, nullable=False, unique=True),
    Column("prev_hash", String, nullable=False),
    Column("payload", Text, nullable=False),
)


class DuplicateEntryError(Exception):
    """append() was called with an entry_id already recorded in the ledger.

    The idempotency signal for webhook dedupe: a check-then-append has a
    race window (two Razorpay webhook retries landing concurrently can both
    pass an `already_processed` pre-check before either commits), so this
    is raised from the UNIQUE constraint on entry_id at insert time, not
    from the pre-check. Callers should treat it as a successful no-op.
    """

_TRIGGERS = (
    """
    CREATE TRIGGER IF NOT EXISTS ledger_entries_no_update
    BEFORE UPDATE ON ledger_entries
    BEGIN
        SELECT RAISE(ABORT, 'ledger_entries is append-only: UPDATE rejected');
    END;
    """,
    """
    CREATE TRIGGER IF NOT EXISTS ledger_entries_no_delete
    BEFORE DELETE ON ledger_entries
    BEGIN
        SELECT RAISE(ABORT, 'ledger_entries is append-only: DELETE rejected');
    END;
    """,
)

_append_lock = threading.Lock()


def make_engine(db_path: str = ":memory:") -> Engine:
    """SQLite engine with the schema and append-only triggers installed.

    ':memory:' uses StaticPool so the whole process shares one connection
    and one in-memory database, instead of each checkout getting a fresh
    (empty) one -- the default SQLite in-memory behavior otherwise silently
    "forgets" everything between calls.
    """
    if db_path == ":memory:":
        engine = create_engine(
            "sqlite:///:memory:",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
    else:
        engine = create_engine(f"sqlite:///{db_path}")

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    metadata.create_all(engine)
    with engine.begin() as conn:
        for stmt in _TRIGGERS:
            conn.exec_driver_sql(stmt)
    return engine


def get_tip(engine: Engine) -> Optional[LedgerEntry]:
    with engine.connect() as conn:
        row = conn.execute(
            select(ledger_entries.c.payload)
            .order_by(ledger_entries.c.idx.desc())
            .limit(1)
        ).first()
    if row is None:
        return None
    return LedgerEntry.model_validate_json(row.payload)


def append(engine: Engine, entry: LedgerEntry) -> None:
    if compute_entry_hash(entry) != entry.entry_hash:
        raise ValueError(
            f"refusing to store entry {entry.index}: entry_hash does not "
            "match its own canonical fields"
        )

    with _append_lock:
        tip = get_tip(engine)
        expected_index = 0 if tip is None else tip.index + 1
        expected_prev_hash = GENESIS_PREV_HASH if tip is None else tip.entry_hash

        if entry.index != expected_index:
            raise ValueError(
                f"refusing to append out-of-sequence entry: expected index "
                f"{expected_index}, got {entry.index}"
            )
        if entry.prev_hash != expected_prev_hash:
            raise ValueError(
                f"refusing to append entry {entry.index}: prev_hash does not "
                "match the current tip"
            )

        try:
            with engine.begin() as conn:
                conn.execute(
                    ledger_entries.insert().values(
                        idx=entry.index,
                        entry_id=entry.entry_id,
                        entry_hash=entry.entry_hash,
                        prev_hash=entry.prev_hash,
                        payload=entry.model_dump_json(),
                    )
                )
        except IntegrityError as e:
            with engine.connect() as conn:
                already_exists = conn.execute(
                    select(ledger_entries.c.idx).where(
                        ledger_entries.c.entry_id == entry.entry_id
                    )
                ).first()
            if already_exists is not None:
                raise DuplicateEntryError(
                    f"entry_id {entry.entry_id!r} already recorded at idx "
                    f"{already_exists.idx}"
                ) from e
            raise


def load_all(engine: Engine) -> list[LedgerEntry]:
    with engine.connect() as conn:
        rows = conn.execute(
            select(ledger_entries.c.payload).order_by(ledger_entries.c.idx)
        ).all()
    return [LedgerEntry.model_validate_json(r.payload) for r in rows]
