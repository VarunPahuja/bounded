"""Phase 6 (docs/PHASE6-PLAN.md): every corpus file must validate, ids must
be globally unique across the whole corpus, and PipelineInput must never be
able to carry injection_context -- structurally, not just by convention.
"""

from pathlib import Path

from eval.runner import SCENARIOS_DIR
from eval.scenario import PipelineInput, Scenario


def _load_all() -> list[Scenario]:
    paths = sorted(SCENARIOS_DIR.glob("*.json"))
    assert paths, f"no scenario files found in {SCENARIOS_DIR}"
    return [Scenario.model_validate_json(p.read_text(encoding="utf-8")) for p in paths]


def test_every_scenario_file_validates():
    scenarios = _load_all()
    assert len(scenarios) > 0


def test_scenario_ids_globally_unique():
    scenarios = _load_all()
    ids = [s.scenario_id for s in scenarios]
    assert len(ids) == len(set(ids)), f"duplicate scenario_id(s): {sorted(ids)}"


def test_action_ids_globally_unique():
    scenarios = _load_all()
    ids = [spec.action_id for s in scenarios for spec in s.actions]
    duplicates = {a for a in ids if ids.count(a) > 1}
    assert not duplicates, f"duplicate action_id(s) across corpus: {sorted(duplicates)}"


def test_pipeline_input_never_carries_injection_context():
    assert "injection_context" not in PipelineInput.model_fields


def test_pipeline_input_round_trips_actions_without_injection_context():
    scenario = next(
        s
        for s in _load_all()
        if s.injection_context
    )
    pipeline_input = scenario.pipeline_input()
    assert isinstance(pipeline_input, PipelineInput)
    assert len(pipeline_input.actions) == len(scenario.actions)
    assert not hasattr(pipeline_input, "injection_context")
