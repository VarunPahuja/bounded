"""Record/replay for eval/runner.py's two LLM call sites: policy/parse.py's
_complete (patched for the "ours" trials) and eval/baseline_llm_judge.py's
_complete (the judge baseline). NOT a reuse of tests/policy/cassette.py --
deliberately, for two reasons:

1. tests/policy/cassette.py records ONE canonical response per key. Replaying
   that 8x for pass^k would return the same sample every time, collapsing
   every scenario's pass^k to a trivial 0%/100% and destroying the exact
   measurement this phase exists to make. This module keeps N_SAMPLES=8
   distinct recorded samples per key, one per trial.
2. tests/policy/cassette.py is pytest-only (a fixture-installed monkeypatch).
   `python -m eval.runner` must run in replay mode standalone, outside
   pytest, from a clean clone -- it cannot depend on a conftest fixture.

EVAL_MODE (env var, default "replay") -- deliberately a different var name
from Phase 5's PARSE_MODE, which stays scoped to tests/policy/:
  replay -- load the one committed cassette file for this key, index
            samples[sample_index]. A miss (no file, or sample_index out of
            range) raises loudly -- it never wraps around or reuses a
            sample, which would correlate trials and distort pass^k.
  record -- on first call for a key (cache miss in the in-process cache),
            fire all N_SAMPLES live calls immediately and write them all to
            one cassette file; every subsequent call for that key (any
            sample_index) indexes the in-memory list rather than re-firing
            live calls per sample_index.
  live   -- always call through, no cassette read or write. Used by neither
            runner mode directly, but kept for completeness/debugging.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Callable, Literal, Optional

from openai import OpenAIError

CASSETTE_DIR = Path(__file__).parent / "cassettes"
MODE = os.environ.get("EVAL_MODE", "replay")
N_SAMPLES = 8


class ReplayedCallError(OpenAIError):
    """Reconstructed, on replay, from a cassette recording a real provider
    failure -- an instance of OpenAIError so both policy.parse.parse_mandate
    and eval.baseline_llm_judge.judge_action catch it exactly as they would
    the original live failure. Same pattern as tests/policy/cassette.py's
    ReplayedProviderError.
    """


class CassetteError(RuntimeError):
    """A replay-mode cassette miss, or a sample_index beyond what was
    recorded. Never silently falls through to the network and never wraps
    around to reuse an earlier sample -- either would correlate trials and
    invalidate pass^k.
    """


def cassette_key(
    *, call_site: Literal["parse", "judge"], model: str, prompt_version: str, messages: list[dict]
) -> str:
    blob = json.dumps(
        {
            "call_site": call_site,
            "model": model,
            "prompt_version": prompt_version,
            "messages": messages,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:32]


_live_call_count = 0


def reset_live_call_count() -> None:
    global _live_call_count
    _live_call_count = 0


def get_live_call_count() -> int:
    return _live_call_count


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, *, call_site: str, model: str, prompt_version: str, key_context: dict, samples: list) -> None:
    CASSETTE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "call_site": call_site,
                "model": model,
                "prompt_version": prompt_version,
                "key_context": key_context,
                "samples": samples,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


# key -> list of {"kind": "response"|"error", ...} -- populated the first
# time a key is seen in "record" mode, so N_SAMPLES live calls fire once per
# key rather than once per sample_index requested.
_record_cache: dict[str, list[dict]] = {}


def sampled_call(
    real_complete: Callable[[list[dict]], str],
    *,
    call_site: Literal["parse", "judge"],
    model: str,
    prompt_version: str,
    key_context: Optional[dict] = None,
) -> Callable[[list[dict], int], str]:
    """Returns f(messages, sample_index) -> response_text, per the mode
    documented on this module. `real_complete` is the actual network call,
    taking the same `messages` list this wrapper hashes -- callers adapt
    their production _complete (which may take a narrower argument, e.g.
    policy.parse._complete's single mandate_text string) into that shape.
    """

    def f(messages: list[dict], sample_index: int) -> str:
        global _live_call_count
        key = cassette_key(call_site=call_site, model=model, prompt_version=prompt_version, messages=messages)
        path = CASSETTE_DIR / f"{key}.json"

        if MODE == "replay":
            if not path.exists():
                raise CassetteError(
                    f"cassette miss ({key}) for call_site={call_site!r} -- prompt, model, or "
                    "messages changed since this cassette was recorded. Re-record with "
                    "EVAL_MODE=record (needs live credentials)."
                )
            samples = _load(path)["samples"]
            if sample_index >= len(samples):
                raise CassetteError(
                    f"cassette {key} has only {len(samples)} samples, sample_index={sample_index} "
                    "requested -- re-record with a cassette holding at least N_SAMPLES samples."
                )
            sample = samples[sample_index]
            if sample["kind"] == "error":
                raise ReplayedCallError(sample["message"])
            return sample["response"]

        if MODE == "live":
            _live_call_count += 1
            return real_complete(messages)

        if MODE != "record":
            raise CassetteError(f"unknown EVAL_MODE {MODE!r} -- expected replay, record, or live")

        if key not in _record_cache:
            if path.exists():
                # Already recorded in a prior run of `python -m eval.runner
                # --EVAL_MODE=record` (e.g. one interrupted partway through
                # by an unrelated bug downstream) -- reuse it rather than
                # re-firing N_SAMPLES live calls for a key already on disk.
                _record_cache[key] = _load(path)["samples"]
            else:
                samples = []
                for _ in range(N_SAMPLES):
                    _live_call_count += 1
                    try:
                        samples.append({"kind": "response", "response": real_complete(messages)})
                    except OpenAIError as exc:
                        samples.append({"kind": "error", "message": str(exc)})
                _record_cache[key] = samples
                _write(
                    path,
                    call_site=call_site,
                    model=model,
                    prompt_version=prompt_version,
                    key_context=key_context or {},
                    samples=samples,
                )

        sample = _record_cache[key][sample_index]
        if sample["kind"] == "error":
            raise ReplayedCallError(sample["message"])
        return sample["response"]

    return f
