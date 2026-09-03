"""Evidence surface backend (task brief Phase 7b, item 2).

Parses the committed docs/EVAL.md -- the actual file eval/report.py
generates from a real eval/runner.py run -- rather than hardcoding any
number. If docs/EVAL.md is regenerated, this endpoint's numbers change
with it; nothing here is a second source of truth for anything eval/report.py
already produces. Regexes are written against the exact markdown shapes
eval/report.py's own section renderers emit (see eval/report.py), not a
generic markdown parser, since the file has one producer and its shape is
known.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

EVAL_MD_PATH = Path(__file__).resolve().parent.parent / "docs" / "EVAL.md"

_PASS_K_VALUES = ("1", "4", "8")


class EvalSummaryUnavailable(Exception):
    """docs/EVAL.md is missing, or doesn't match the shape eval/report.py
    produces -- surfaced to the caller rather than papered over with a
    placeholder number."""


class ClassBalance(BaseModel):
    class_label: str
    scenarios: int
    pct: float


class CorpusBalance(BaseModel):
    classes: list[ClassBalance]
    total: int
    benign_pct: float


class FalsePositiveRow(BaseModel):
    pipeline: str
    fp: int
    n: int
    rate_pct: float
    ci_lo: float
    ci_hi: float


class PassKRow(BaseModel):
    class_label: str
    ours: dict[str, float]
    judge: dict[str, float]


class EvalSummary(BaseModel):
    n_scenarios: int
    n_samples: int
    generated_at: str
    mode: str
    commit: str
    corpus: CorpusBalance
    unsound_safe_ours: int
    unsound_safe_judge: int
    unsound_safe_definition: str
    false_positive: list[FalsePositiveRow]
    pass_k: list[PassKRow]
    median_latency_ms: float
    median_latency_n: int
    adversarial_note: str


def _require(pattern: str, text: str, flags: int = 0) -> re.Match:
    m = re.search(pattern, text, flags)
    if not m:
        raise EvalSummaryUnavailable(
            f"docs/EVAL.md did not match the shape eval/report.py produces (pattern: {pattern!r})"
        )
    return m


def _parse_header(text: str) -> dict:
    m = _require(
        r"generated: (?P<gen>[^|]+)\| mode: (?P<mode>[^|]+)\| commit: (?P<commit>[^|]+)\| "
        r"scenarios: (?P<n>\d+) \| samples/scenario: (?P<samples>\d+)",
        text,
    )
    return {
        "generated_at": m.group("gen").strip(),
        "mode": m.group("mode").strip(),
        "commit": m.group("commit").strip(),
        "n_scenarios": int(m.group("n")),
        "n_samples": int(m.group("samples")),
    }


def _parse_corpus_balance(text: str) -> CorpusBalance:
    section = _require(r"## Corpus balance\n(.*?)\n## ", text, re.DOTALL).group(1)
    classes = [
        ClassBalance(class_label=m.group(1), scenarios=int(m.group(2)), pct=float(m.group(3)))
        for m in re.finditer(r"\| ([a-z_]+) \| (\d+) \| ([\d.]+)% \|", section)
    ]
    total_m = _require(r"\*\*total\*\* \| \*\*(\d+)\*\*", section)
    benign_m = _require(r"Benign share: ([\d.]+)%", section)
    return CorpusBalance(classes=classes, total=int(total_m.group(1)), benign_pct=float(benign_m.group(1)))


def _parse_unsound_safe(text: str) -> tuple[int, int, str]:
    section = _require(r"## Unsound-safe verdicts\n\n(.*?)\n## ", text, re.DOTALL).group(1)
    definition_m = _require(r"^(An unsound-safe verdict is .+?)\n", section, re.MULTILINE)
    ours_m = _require(r"\*\*[Oo][Uu][Rr][Ss]:\s*(\d+)", section)
    judge_m = _require(r"the ours count is\):\s*(\d+)", section)
    return int(ours_m.group(1)), int(judge_m.group(1)), definition_m.group(1).strip()


def _parse_false_positive(text: str) -> list[FalsePositiveRow]:
    section = _require(r"## False positive rate on benign flows\n(.*?)\n## ", text, re.DOTALL).group(1)
    rows = []
    for m in re.finditer(
        r"\| (ours|judge) \| (\d+) \| (\d+) \| ([\d.]+)% \| ([\d.]+) - ([\d.]+) \|", section
    ):
        rows.append(
            FalsePositiveRow(
                pipeline=m.group(1),
                fp=int(m.group(2)),
                n=int(m.group(3)),
                rate_pct=float(m.group(4)),
                ci_lo=float(m.group(5)),
                ci_hi=float(m.group(6)),
            )
        )
    if not rows:
        raise EvalSummaryUnavailable("docs/EVAL.md false-positive table did not parse")
    return rows


def _parse_pass_k(text: str) -> list[PassKRow]:
    section = _require(r"## pass\^k .*?\n(.*?)\n\npass\^k is computed", text, re.DOTALL).group(1)
    rows = []
    row_pattern = (
        r"\| \*{0,2}([a-zA-Z_]+)\*{0,2} \| ([\d.]+)% \| ([\d.]+)% \| ([\d.]+)% \| "
        r"([\d.]+)% \| ([\d.]+)% \| ([\d.]+)% \|"
    )
    for m in re.finditer(row_pattern, section):
        label = m.group(1)
        if label == "Class":
            continue
        values = [float(m.group(i)) for i in range(2, 8)]
        rows.append(
            PassKRow(
                class_label=label,
                ours=dict(zip(_PASS_K_VALUES, values[0:3])),
                judge=dict(zip(_PASS_K_VALUES, values[3:6])),
            )
        )
    if not rows:
        raise EvalSummaryUnavailable("docs/EVAL.md pass^k table did not parse")
    return rows


def _parse_latency(text: str) -> tuple[float, int]:
    m = _require(
        r"## Median verification latency \(ours, Z3 only\)\s*\n\n([\d.]+) ms \(n=(\d+) verify_action calls\)",
        text,
    )
    return float(m.group(1)), int(m.group(2))


def _parse_adversarial_note(text: str) -> str:
    m = _require(
        r"(## adversarial_vs_ours: findings and what the 100% means\n.*?)\n## ", text, re.DOTALL
    )
    return m.group(1).strip()


def load_eval_summary(path: Optional[Path] = None) -> EvalSummary:
    md_path = path or EVAL_MD_PATH
    if not md_path.exists():
        raise EvalSummaryUnavailable(f"{md_path} does not exist -- run `python -m eval.runner` first")
    text = md_path.read_text(encoding="utf-8")

    header = _parse_header(text)
    corpus = _parse_corpus_balance(text)
    unsound_ours, unsound_judge, definition = _parse_unsound_safe(text)
    fp = _parse_false_positive(text)
    pass_k = _parse_pass_k(text)
    latency_ms, latency_n = _parse_latency(text)
    adversarial_note = _parse_adversarial_note(text)

    return EvalSummary(
        **header,
        corpus=corpus,
        unsound_safe_ours=unsound_ours,
        unsound_safe_judge=unsound_judge,
        unsound_safe_definition=definition,
        false_positive=fp,
        pass_k=pass_k,
        median_latency_ms=latency_ms,
        median_latency_n=latency_n,
        adversarial_note=adversarial_note,
    )
