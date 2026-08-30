"""Symbolic payment transition system for bounded model checking.

State: month_spend, captured[order_slot], refunded[order_slot].
Transitions: create_order, capture, refund.

NUM_ORDER_SLOTS bounds the order universe so per-order sums stay finite Z3
arrays rather than an unbounded map — see ADR-0007. MAX_AMOUNT_PAISE
bounds each step's free amount variable — see ADR-0008. category_idx's
bound is policy-dependent, not global — see ADR-0009: a policy's
allowed/blocked categories are already a small, exact, known set, so the
domain is built from the policy itself rather than an arbitrary constant.

Money is Int paise throughout. Never Real, never float. See CLAUDE.md.

PolicyIR (contracts/models.py, frozen) is the only policy type this
module accepts. Phase 1's HandPolicy is gone — it was a hand-picked
subset that existed only because the real IR wasn't wired up yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from z3 import And, ArithRef, If, Int, Or, Solver

from contracts.models import PolicyIR

NUM_ORDER_SLOTS = 2
MAX_AMOUNT_PAISE = 10_000_000  # 100,000 rupees; keeps the search finite

ACTION_CREATE_ORDER = 0
ACTION_CAPTURE = 1
ACTION_REFUND = 2
ACTION_TYPES = (ACTION_CREATE_ORDER, ACTION_CAPTURE, ACTION_REFUND)


def category_vocabulary(policy: PolicyIR) -> list[str]:
    """Named categories this policy actually restricts on, in index
    order. Index len(vocabulary) — one past the end — is the OTHER
    sentinel: any category the policy doesn't name.
    """
    names: list[str] = []
    for name in list(policy.allowed_categories or []) + list(policy.blocked_categories):
        if name not in names:
            names.append(name)
    return names


@dataclass
class StepVars:
    """Free per-step action variables. Z3 chooses these; a guard
    constrains which choices are admissible before the transition fires.
    """

    action_type: ArithRef
    order_idx: ArithRef
    amount_paise: ArithRef
    category_idx: ArithRef


@dataclass
class State:
    """Accumulated state at one time index."""

    month_spend: ArithRef
    captured: list[ArithRef]
    refunded: list[ArithRef]


def build_symbolic_system(policy: PolicyIR, horizon: int) -> tuple[Solver, list[StepVars], list[State]]:
    """Declares state/step variables for `horizon` steps and asserts the
    initial state plus input bounds. Does not assert the transition
    relation or any guard — callers add those.

    Takes `policy` (not just `horizon`) because category_idx's bound is
    the policy's own category vocabulary size, not a fixed constant.
    """

    vocabulary_size = len(category_vocabulary(policy))

    solver = Solver()
    solver.set("timeout", 30_000)

    steps = [
        StepVars(
            action_type=Int(f"action_type_{t}"),
            order_idx=Int(f"order_idx_{t}"),
            amount_paise=Int(f"amount_paise_{t}"),
            category_idx=Int(f"category_idx_{t}"),
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
        solver.add(sv.category_idx >= 0, sv.category_idx <= vocabulary_size)

    return solver, steps, states


def add_transition_relation(solver: Solver, steps: list[StepVars], states: list[State]) -> None:
    """Frame-conditioned transition relation: every state variable is
    constrained at every step, either updated by the action or explicitly
    held unchanged. No variable is left free between steps.

    category_idx carries no state of its own — it's a per-step input,
    like amount_paise — so it needs no frame condition here.
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
