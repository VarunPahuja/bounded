"""Persistent status strip backend (task brief Phase 7b, item 3): "46
scenarios · 114 tests · 0 unsound-safe · ~10ms median proof · chain
verified" -- every figure pulled from something real, not a constant.

scenario_count counts eval/scenarios/*.json directly (always available,
no dependency on docs/EVAL.md having been regenerated). test_count runs
pytest --collect-only once per backend process and caches the result --
collection only, no test execution, so it stays cheap while still being a
real count rather than a hardcoded "114". unsound_safe/median_latency_ms
come from api.eval_summary's parse of the committed docs/EVAL.md and are
None (never a fabricated 0) if that file is missing. chain_verified calls
the real ledger.chain.verify_chain result on every request -- deliberately
never cached, since the Ledger surface's own actions (seeding, and a
tampered *real* write, were one ever made outside the preview path) could
change it within a session.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from api.attacks import SCENARIOS_DIR
from api.eval_summary import EvalSummaryUnavailable, load_eval_summary
from api.ledger_backend import get_chain_status

REPO_ROOT = Path(__file__).resolve().parent.parent

_test_count_cache: Optional[int] = None


def _collect_test_count() -> Optional[int]:
    global _test_count_cache
    if _test_count_cache is not None:
        return _test_count_cache
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except Exception:
        return None
    m = re.search(r"(\d+) tests? collected", result.stdout)
    if not m:
        return None
    _test_count_cache = int(m.group(1))
    return _test_count_cache


class StatusSummary(BaseModel):
    scenario_count: int
    test_count: Optional[int]
    unsound_safe: Optional[int]
    median_latency_ms: Optional[float]
    chain_verified: bool


def get_status_summary() -> StatusSummary:
    scenario_count = len(list(SCENARIOS_DIR.glob("*.json")))
    test_count = _collect_test_count()

    try:
        eval_summary = load_eval_summary()
        unsound_safe: Optional[int] = eval_summary.unsound_safe_ours
        median_latency_ms: Optional[float] = eval_summary.median_latency_ms
    except EvalSummaryUnavailable:
        unsound_safe = None
        median_latency_ms = None

    chain = get_chain_status()

    return StatusSummary(
        scenario_count=scenario_count,
        test_count=test_count,
        unsound_safe=unsound_safe,
        median_latency_ms=median_latency_ms,
        chain_verified=chain.broken_at_index is None,
    )
