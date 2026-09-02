"""eval/cassette.py's N_SAMPLES must match eval/runner.py's -- pass^k needs
n >= max(k) = 8, and if these ever drifted apart, sampled_call would be
recording (or expecting to replay) a different sample count than the runner
actually iterates over.
"""

from eval.cassette import N_SAMPLES as CASSETTE_N_SAMPLES
from eval.runner import N_SAMPLES as RUNNER_N_SAMPLES


def test_cassette_and_runner_agree_on_sample_count():
    assert CASSETTE_N_SAMPLES == RUNNER_N_SAMPLES == 8
