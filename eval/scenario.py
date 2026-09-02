"""Eval-only scenario bookkeeping (Phase 6, docs/PHASE6-PLAN.md). No change to
contracts/models.py -- a Scenario is a corpus fixture built around existing
frozen types (Action, ActionType), not a new frozen shape.

STRUCTURAL ENFORCEMENT that our pipeline can never read injection_context:
Scenario.pipeline_input() returns a PipelineInput, which has no such field --
eval.runner.run_ours_trial is typed to take a PipelineInput (via
Scenario.pipeline_input()), not a Scenario, so the omission is structurally
unreachable, not just a naming convention nobody happened to violate yet.
test_scenario_schema.py and tests/test_architecture.py both pin this, from
two different angles: the type itself, and an AST walk of the function that
must never read the field.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from contracts.models import Action, ActionType


class ScenarioClass(str, Enum):
    OVER_CAP = "over_cap"
    REFUND_EXCEEDS_CAPTURE = "refund_exceeds_capture"
    PROMPT_INJECTION = "prompt_injection"
    CATEGORY_COUNT_VIOLATION = "category_count_violation"
    BENIGN = "benign"


class ScenarioActionSpec(BaseModel):
    """One action in a scenario's script, plus the verdict it should produce
    against our pipeline. expected_decision is the label authored into the
    corpus -- it is never derived from a live run, so a scenario's own intent
    stays legible from the JSON file alone.
    """

    model_config = ConfigDict(extra="forbid")

    action_id: str
    action_type: ActionType
    order_id: str
    amount_paise: int = Field(gt=0)
    category: Optional[str] = None
    occurred_at: datetime
    expected_decision: Literal["allow", "block"]

    def to_action(self) -> Action:
        return Action(
            action_id=self.action_id,
            action_type=self.action_type,
            order_id=self.order_id,
            amount_paise=self.amount_paise,
            category=self.category,
            occurred_at=self.occurred_at,
        )


class PipelineInput(BaseModel):
    """The only view of a scenario eval/runner.py's ours-pipeline function
    may accept. No injection_context field -- the omission is the
    enforcement mechanism, not a filter that could be forgotten.
    """

    model_config = ConfigDict(extra="forbid")

    mandate_text: str
    actions: list[Action]


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    class_label: ScenarioClass
    mandate_text: str
    actions: list[ScenarioActionSpec] = Field(default_factory=list)
    # action_id -> poisoned text. JUDGE-ONLY: see PipelineInput above and
    # eval.baseline_llm_judge, the one function permitted to read this.
    injection_context: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _actions_non_empty(self) -> "Scenario":
        if not self.actions:
            raise ValueError(f"scenario {self.scenario_id!r} has no actions")
        return self

    @model_validator(mode="after")
    def _action_ids_unique(self) -> "Scenario":
        ids = [a.action_id for a in self.actions]
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate action_id within scenario {self.scenario_id!r}: {ids}")
        return self

    @model_validator(mode="after")
    def _injection_context_only_for_injection_class(self) -> "Scenario":
        if self.injection_context and self.class_label != ScenarioClass.PROMPT_INJECTION:
            raise ValueError(
                f"scenario {self.scenario_id!r} sets injection_context but "
                f"class_label is {self.class_label.value!r}, not 'prompt_injection'"
            )
        return self

    @model_validator(mode="after")
    def _injection_context_keys_reference_real_actions(self) -> "Scenario":
        action_ids = {a.action_id for a in self.actions}
        unknown = set(self.injection_context) - action_ids
        if unknown:
            raise ValueError(
                f"scenario {self.scenario_id!r}: injection_context references "
                f"unknown action_id(s) {sorted(unknown)}"
            )
        return self

    def pipeline_input(self) -> PipelineInput:
        return PipelineInput(
            mandate_text=self.mandate_text,
            actions=[a.to_action() for a in self.actions],
        )
