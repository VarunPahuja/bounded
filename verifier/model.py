"""Symbolic payment transition system for Phase 1 bounded model checking.

State: month_spend, captured[order_slot], refunded[order_slot].
Transitions: create_order, capture, refund.

NUM_ORDER_SLOTS bounds the order universe so per-order sums stay finite Z3
arrays rather than an unbounded map. MAX_AMOUNT_PAISE bounds each step's
free amount variable — an unbounded Int turns unsat into unknown.

Money is Int paise throughout. Never Real, never float. See CLAUDE.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from z3 import And, ArithRef, If, Int, Or, Solver

NUM_ORDER_SLOTS = 2
MAX_AMOUNT_PAISE = 10_000_000  # 100,000 rupees; keeps the search finite

ACTION_CREATE_ORDER = 0
ACTION_CAPTURE = 1
ACTION_REFUND = 2
ACTION_TYPES = (ACTION_CREATE_ORDER, ACTION_CAPTURE, ACTION_REFUND)


@dataclass(frozen=True)
class HandPolicy:
    """Hand-written policy constraints for Phase 1. Not PolicyIR — Phase 2
    wires the general typed IR to this same transition system.
    """

    per_txn_cap_paise: Optional[int] = None
    window_cap_paise: Optional[int] = None
    allowed_categories: Optional[list[str]] = None
    blocked_categories: list[str] = field(default_factory=list)


@dataclass
class StepVars:
    """Free per-step action variables. Z3 chooses these; a guard
    constrains which choices are admissible before the transition fires.
    """

    action_type: ArithRef
    order_idx: ArithRef
    amount_paise: ArithRef


@dataclass
class State:
    """Accumulated state at one time index."""

    month_spend: ArithRef
    captured: list[ArithRef]
    refunded: list[ArithRef]


def build_symbolic_system(horizon: int) -> tuple[Solver, list[StepVars], list[State]]:
    """Declares state/step variables for `horizon` steps and asserts the
    initial state plus input bounds. Does not assert the transition
    relation or any guard — callers add those.
    """

    solver = Solver()
    solver.set("timeout", 30_000)

    steps = [
        StepVars(
            action_type=Int(f"action_type_{t}"),
            order_idx=Int(f"order_idx_{t}"),
            amount_paise=Int(f"amount_paise_{t}"),
        )
        for t in range(horizon)
    ]
    states = [
        State(
            month_spend=Int(f"month_spend_{t}"),
            captured=[Int(f"captured_{slot}_{t}") for slot in range(NUM_ORDER_SLOTS)],
            refunded=[Int(f"refunded_{slot}_{t}") for slot in range(NUM_ORDER_SLOTS)],
        )
        for t in range(horizon + 1)
    ]

    solver.add(states[0].month_spend == 0)
    for slot in range(NUM_ORDER_SLOTS):
        solver.add(states[0].captured[slot] == 0)
        solver.add(states[0].refunded[slot] == 0)

    for sv in steps:
        solver.add(Or(*(sv.action_type == kind for kind in ACTION_TYPES)))
        solver.add(sv.order_idx >= 0, sv.order_idx < NUM_ORDER_SLOTS)
        solver.add(sv.amount_paise >= 0, sv.amount_paise <= MAX_AMOUNT_PAISE)

    return solver, steps, states


def add_transition_relation(solver: Solver, steps: list[StepVars], states: list[State]) -> None:
    """Frame-conditioned transition relation: every state variable is
    constrained at every step, either updated by the action or explicitly
    held unchanged. No variable is left free between steps.
    """

    for t, sv in enumerate(steps):
        s0, s1 = states[t], states[t + 1]
        is_capture = sv.action_type == ACTION_CAPTURE
        is_refund = sv.action_type == ACTION_REFUND

        solver.add(s1.month_spend == If(is_capture, s0.month_spend + sv.amount_paise, s0.month_spend))

        for slot in range(NUM_ORDER_SLOTS):
            targets_slot = sv.order_idx == slot
            solver.add(
                s1.captured[slot]
                == If(And(is_capture, targets_slot), s0.captured[slot] + sv.amount_paise, s0.captured[slot])
            )
            solver.add(
                s1.refunded[slot]
                == If(And(is_refund, targets_slot), s0.refunded[slot] + sv.amount_paise, s0.refunded[slot])
            )
