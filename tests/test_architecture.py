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


# ============================================================
# ADR-0005: the LLM proposes structure, the solver decides. Phase 5 is
# where that rule is easiest to violate while looking reasonable --
# verifier/ must never be able to reach policy/parse.py or an LLM client,
# by any import path.
# ============================================================

_LLM_CLIENT_MODULES = {"openai"}


def _iter_verifier_python_files():
    for path in (REPO_ROOT / "verifier").rglob("*.py"):
        if ".venv" in path.parts:
            continue
        yield path


def _flagged_module(module: str) -> bool:
    if module == "policy.parse" or module.startswith("policy.parse."):
        return True
    return any(module == m or module.startswith(f"{m}.") for m in _LLM_CLIENT_MODULES)


def _forbidden_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and _flagged_module(node.module):
            hits.append(f"from {node.module} import ...")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if _flagged_module(alias.name):
                    hits.append(f"import {alias.name}")
    return hits


def test_parse_is_not_in_enforcement_path():
    violations = {}
    for path in _iter_verifier_python_files():
        hits = _forbidden_imports(path)
        if hits:
            violations[str(path.relative_to(REPO_ROOT))] = hits

    assert not violations, (
        "verifier/ must never import policy/parse.py or an LLM client -- "
        f"the solver decides, the LLM only proposes structure (ADR-0005): {violations}"
    )
