"""MASTER.md Phase 6: benign flows are at least 30% of the corpus, and all
five ScenarioClass values are represented. Deliberately no hardcoded corpus
size -- both checks hold whether the corpus has 18 scenarios (this pilot) or
60-100 (the eventual full corpus), so nothing here needs to change when it
scales.
"""

from eval.runner import load_corpus
from eval.scenario import ScenarioClass


def test_benign_at_least_30_percent():
    scenarios = load_corpus()
    benign = sum(1 for s in scenarios if s.class_label == ScenarioClass.BENIGN)
    assert benign / len(scenarios) >= 0.30, (
        f"benign share is {benign}/{len(scenarios)} = {100 * benign / len(scenarios):.1f}%, below 30%"
    )


def test_all_five_classes_represented():
    scenarios = load_corpus()
    present = {s.class_label for s in scenarios}
    missing = set(ScenarioClass) - present
    assert not missing, f"scenario classes missing from the corpus: {sorted(c.value for c in missing)}"
