"""Repo-wide architectural invariants -- not one module's unit tests, but
rules CLAUDE.md and the ADRs treat as load-bearing across the whole
codebase. Statically enforced, same class of guarantee as CLAUDE.md's
"verifier/ must never import policy/parse.py" rule (see ADR-0003's
"Negative / accepted costs" section for why this is a CI-run test rather
than a language-level sandbox, and why that's an accepted, stated cost
rather than a hidden gap).
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

_GATED_RAIL_NAMES = {"attempt_capture", "refund"}

_ALLOWED_RAIL_IMPORTERS = {
    REPO_ROOT / "rail" / "interceptor.py",
    REPO_ROOT / "rail" / "razorpay_client.py",  # defines them; not an import of itself
    # Phase 3's live rail test exists specifically to prove the rail works
    # in isolation -- CLAUDE.md bans mocking that call, which means it has
    # to be allowed to reach attempt_capture/refund directly.
    REPO_ROOT / "tests" / "rail" / "test_razorpay_client_live.py",
}


def _iter_repo_python_files():
    for path in REPO_ROOT.rglob("*.py"):
        if ".venv" in path.parts:
            continue
        yield path


def _imports_gated_rail_names(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "rail.razorpay_client":
            if any(alias.name in _GATED_RAIL_NAMES for alias in node.names):
                return True
        if isinstance(node, ast.Import):
            if any(alias.name == "rail.razorpay_client" for alias in node.names):
                # Whole-module import of rail.razorpay_client: not used
                # anywhere legitimately (create_order, the one thing
                # scripts/seed.py needs, is imported by name), so flag it
                # too rather than trying to trace attribute access.
                return True
    return False


def test_no_direct_rail_access():
    violations = []
    for path in _iter_repo_python_files():
        if path in _ALLOWED_RAIL_IMPORTERS:
            continue
        if _imports_gated_rail_names(path):
            violations.append(str(path.relative_to(REPO_ROOT)))

    assert not violations, (
        "attempt_capture/refund (or a whole-module import of "
        "rail.razorpay_client) found outside the interceptor gate -- see "
        f"ADR-0003: {violations}"
    )
