"""Record/replay for policy/parse.py's Azure OpenAI calls -- the eval-harness
skill's cassette pattern, scaled down to Phase 5's ten fixture mandates.
policy/parse.py itself knows nothing about cassettes; production code always
calls the real endpoint. Tests monkeypatch policy.parse._complete with the
wrapper this module builds.

PARSE_MODE (env var, default "replay"):
  replay -- load a committed cassette keyed by (model, prompt_version,
            mandate text). A miss raises -- it never silently falls
            through to the network, so a stale prompt shows up as a loud
            failure telling you to re-record, not a quiet pass against
            the wrong recording.
  record -- call the real endpoint and write the cassette.

A cassette records either a successful response or a provider-side error
(kind: "response" | "error"). The error shape exists because a real call
can fail before returning any text -- observed live (2026-09-01): Azure's
content filter rejected the prompt-injection fixture outright with a
BadRequestError, never reaching the model. Only caching the success path
would mean that case re-hits the network on every replay run (or worse,
"passes" for the wrong reason if the network happens to be unreachable and
some other code path swallows the failure) instead of deterministically
reproducing the same provider error offline.

tests/policy/test_parse_live.py uses neither: it calls policy.parse._complete
unpatched, straight through to Azure, and is skipped without credentials.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Callable

from openai import OpenAIError

CASSETTE_DIR = Path(__file__).parent / "cassettes"
MODE = os.environ.get("PARSE_MODE", "replay")


class ReplayedProviderError(OpenAIError):
    """Reconstructed, on replay, from a cassette recording a real provider
    error -- an instance of OpenAIError so policy.parse.parse_mandate's
    `except OpenAIError` catches it exactly as it would the original.
    """


def cassette_key(*, model: str, prompt_version: str, mandate_text: str) -> str:
    blob = json.dumps(
        {"model": model, "prompt_version": prompt_version, "mandate_text": mandate_text},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:32]


def cassette_backed(
    real_complete: Callable[[str], str], *, model: str, prompt_version: str
) -> Callable[[str], str]:
    def wrapped(mandate_text: str) -> str:
        key = cassette_key(model=model, prompt_version=prompt_version, mandate_text=mandate_text)
        path = CASSETTE_DIR / f"{key}.json"

        if MODE == "replay":
            if not path.exists():
                raise RuntimeError(
                    f"cassette miss ({key}) for mandate {mandate_text!r} -- prompt or "
                    "mandate text changed since this cassette was recorded. "
                    "Re-record with PARSE_MODE=record (needs Azure credentials)."
                )
            record = json.loads(path.read_text(encoding="utf-8"))
            if record["kind"] == "error":
                raise ReplayedProviderError(record["message"])
            return record["response"]

        try:
            response = real_complete(mandate_text)
        except OpenAIError as exc:
            if MODE == "record":
                _write(path, mandate_text, kind="error", message=str(exc))
            raise

        if MODE == "record":
            _write(path, mandate_text, kind="response", response=response)
        return response

    return wrapped


def _write(path: Path, mandate_text: str, *, kind: str, **fields) -> None:
    CASSETTE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"mandate_text": mandate_text, "kind": kind, **fields},
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
