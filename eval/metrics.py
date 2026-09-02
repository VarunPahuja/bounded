"""Pure metrics, no I/O. pass^k (tau-bench definition) and the Wilson
interval used to report it -- adapted from
.claude/skills/eval-harness/SKILL.md's reference implementation.
"""

from __future__ import annotations

from math import comb, sqrt


def pass_hat_k(n: int, c: int, k: int) -> float:
    """tau-bench pass^k = C(c,k)/C(n,k): the probability that ALL k of a
    randomly chosen k-subset of n independent trials succeed -- NOT
    HumanEval's pass@k ("at least one succeeds"). Measures reliability
    across repeated, otherwise-identical attempts, which is exactly what
    re-parsing the same mandate (or re-judging the same action) n times
    tests.

    0.0 if k > c: not enough successes to fill an all-success k-subset.
    Raises if k > n: not enough trials to form a k-subset at all -- a
    configuration error, never silently coerced to something smaller.
    """
    if k > n:
        raise ValueError(f"k={k} exceeds n={n} trials")
    if k > c:
        return 0.0
    return comb(c, k) / comb(n, k)


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = successes / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, centre - half), min(1.0, centre + half)
