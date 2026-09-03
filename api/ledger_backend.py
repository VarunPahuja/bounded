"""Ledger surface backend (docs/PHASE7-PLAN.md).

Reads the persistent demo ledger (api/demo_state.demo_engine) via
ledger.store.load_all and ledger.chain.verify_chain -- no new decision
logic. _seed_if_empty appends a handful of real propose_action calls
(same mocked-rail pattern as api/attacks.py, ADR-0014) the first time the
ledger is read, so the surface has real, varied entries -- an allow, a
refund, a block -- rather than only genesis.

tamper_preview never writes to the real store (ledger/store.py's own
append-only triggers would reject a real UPDATE anyway). It mutates an
in-memory copy of the loaded entries and re-verifies that copy, which
demonstrates exactly where the chain would break if the same edit were
made directly against the database, bypassing the application layer --
the task brief's "control that mutates an entry and shows the chain
breaking at that index," built without touching the append-only
guarantee it demonstrates.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from unittest.mock import patch

from pydantic import BaseModel

from contracts.models import Action, ActionType, LedgerEntry, PolicyIR
from ledger.chain import verify_chain
from ledger.store import load_all
from rail.interceptor import propose_action
from rail.razorpay_client import CaptureResult

from api.demo_state import demo_engine, demo_private_key, demo_public_key
from api.z3_lock import Z3_LOCK

# A fixed demo policy for seeding only -- not user-editable here. The
# Mandate/Proof surfaces are where a viewer explores arbitrary policies;
# this one exists solely to give the Ledger surface real, varied entries.
_SEED_POLICY = PolicyIR(per_txn_cap_paise=500_000, window_cap_paise=1_500_000, window="month")


def _mock_capture(payment_id: str, amount_paise: int) -> CaptureResult:
    return CaptureResult(success=True, payment={"id": f"pay_{payment_id}", "status": "captured"})


def _mock_refund(payment_id: str, amount_paise: int) -> dict:
    return {"id": f"pay_{payment_id}_refund", "status": "refunded"}


def _seed_if_empty() -> None:
    engine = demo_engine()
    if len(load_all(engine)) > 1:  # more than just genesis
        return

    private_key = demo_private_key()
    now = lambda: datetime.now(timezone.utc)  # noqa: E731
    seed_actions = [
        Action(action_id="seed-1", action_type=ActionType.CAPTURE, order_id="order_demo_a",
               amount_paise=320000, category="groceries", occurred_at=now()),
        Action(action_id="seed-2", action_type=ActionType.CAPTURE, order_id="order_demo_b",
               amount_paise=180000, category="utilities", occurred_at=now()),
        Action(action_id="seed-3", action_type=ActionType.REFUND, order_id="order_demo_a",
               amount_paise=50000, category="groceries", occurred_at=now()),
        # Exceeds _SEED_POLICY's Rs 5,000 per-txn cap -- deliberately blocked,
        # so the seeded ledger shows both an ALLOW and a BLOCK decision.
        Action(action_id="seed-4", action_type=ActionType.CAPTURE, order_id="order_demo_c",
               amount_paise=600000, category="electronics", occurred_at=now()),
    ]
    with patch("rail.interceptor.attempt_capture", side_effect=_mock_capture), patch(
        "rail.interceptor.refund", side_effect=_mock_refund
    ), Z3_LOCK:
        for action in seed_actions:
            propose_action(action, _SEED_POLICY, engine, private_key)


def get_entries() -> list[LedgerEntry]:
    _seed_if_empty()
    return load_all(demo_engine())


class ChainVerifyResponse(BaseModel):
    broken_at_index: Optional[int] = None


def get_chain_status() -> ChainVerifyResponse:
    entries = load_all(demo_engine())
    return ChainVerifyResponse(broken_at_index=verify_chain(entries, demo_public_key()))


class TamperPreviewResponse(BaseModel):
    broken_at_index: Optional[int] = None
    error: Optional[str] = None


def tamper_preview(index: int, new_amount_paise: int) -> TamperPreviewResponse:
    entries = load_all(demo_engine())
    if index < 0 or index >= len(entries):
        return TamperPreviewResponse(error=f"index {index} out of range")
    target = entries[index]
    if target.action is None:
        return TamperPreviewResponse(error="this entry has no action to tamper with (e.g. genesis)")

    mutated_entry = target.model_copy(
        update={"action": target.action.model_copy(update={"amount_paise": new_amount_paise})}
    )
    tampered = list(entries)
    tampered[index] = mutated_entry

    return TamperPreviewResponse(broken_at_index=verify_chain(tampered, demo_public_key()))
