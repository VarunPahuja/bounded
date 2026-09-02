"""MASTER.md Phase 6: 'Unsound safe verdicts: must be 0. Any nonzero number
here is a bug, not a metric.' This is the one eval-harness test that fails
the build outright, mirroring CLAUDE.md's rule that a violation must never
be marked safe under any circumstance.
"""

import eval.cassette
from eval.runner import load_corpus, run_corpus


def test_no_unsound_safe_verdicts(monkeypatch):
    monkeypatch.setattr(eval.cassette, "MODE", "replay")
    scenarios = load_corpus()
    corpus_result, _ = run_corpus(scenarios)

    details = [
        (sr.scenario_id, i, action_id)
        for sr in corpus_result.scenario_results
        for i, trial in enumerate(sr.ours_trials)
        for action_id in trial.unsound_safe_action_ids
    ]

    assert not details, (
        f"unsound_safe_count={len(details)} -- a stated violation was verified SAFE "
        f"(scenario_id, sample_index, action_id): {details}"
    )
