"""Thin FastAPI orchestration layer for the Phase 7 dashboard
(docs/PHASE7-PLAN.md). Every route is a direct call into an existing
module -- verifier/, rail/, policy/, ledger/ -- with no new decision
logic. CORS allows local dev origins plus any *.vercel.app origin (the
deployed frontend's preview and production URLs both match that
pattern) -- this is a demo backend for a graded submission, not a
service hardened against untrusted traffic.

Run with: uvicorn api.main:app --reload --port 8000
"""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from contracts.models import LedgerEntry, PolicyIR, VerificationResult
from policy.parse import MandateParseError

from api.attacks import AttackRunResult, ScenarioNotFoundError, ScenarioSummary, list_scenarios, run_scenario
from api.eval_summary import EvalSummary, EvalSummaryUnavailable, load_eval_summary
from api.ledger_backend import ChainVerifyResponse, TamperPreviewResponse
from api.ledger_backend import get_chain_status, get_entries, tamper_preview
from api.mandate_cache import DemoMandateResponse
from api.mandates import ParseResponse
from api.mandates import activate as activate_mandate
from api.mandates import demo as demo_mandate
from api.mandates import parse as parse_mandate_text
from api.proof import GuardName
from api.proof import verify as verify_proof
from api.status_summary import StatusSummary, get_status_summary

app = FastAPI(title="Bounded dashboard API")

# CORS_EXTRA_ORIGIN lets the deployed frontend's exact origin be added
# explicitly (Render env var) without widening the regex below to
# anything broader than the *.vercel.app pattern every Vercel deploy of
# this project actually uses.
_extra_origin = os.environ.get("CORS_EXTRA_ORIGIN")
_allow_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
if _extra_origin:
    _allow_origins.append(_extra_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/attack/scenarios", response_model=list[ScenarioSummary])
def get_attack_scenarios() -> list[ScenarioSummary]:
    return list_scenarios()


@app.post("/api/attack/run/{scenario_id}", response_model=AttackRunResult)
def post_attack_run(scenario_id: str) -> AttackRunResult:
    try:
        return run_scenario(scenario_id)
    except ScenarioNotFoundError:
        raise HTTPException(status_code=404, detail=f"unknown scenario_id {scenario_id!r}")
    except MandateParseError as e:
        raise HTTPException(status_code=502, detail=f"mandate parse failed: {e}")


class ParseRequest(BaseModel):
    text: str


@app.post("/api/mandate/parse", response_model=ParseResponse)
def post_mandate_parse(req: ParseRequest) -> ParseResponse:
    return parse_mandate_text(req.text)


class ActivateRequest(BaseModel):
    policy: PolicyIR
    horizon: int = 8


@app.post("/api/mandate/activate", response_model=VerificationResult)
def post_mandate_activate(req: ActivateRequest) -> VerificationResult:
    return activate_mandate(req.policy, horizon=req.horizon)


@app.get("/api/mandate/demo", response_model=DemoMandateResponse)
def get_mandate_demo() -> DemoMandateResponse:
    return demo_mandate()


class ProofVerifyRequest(BaseModel):
    policy: PolicyIR
    guard: GuardName
    horizon: int = 8


@app.post("/api/proof/verify", response_model=VerificationResult)
def post_proof_verify(req: ProofVerifyRequest) -> VerificationResult:
    return verify_proof(req.policy, req.guard, horizon=req.horizon)


@app.get("/api/ledger/entries", response_model=list[LedgerEntry])
def get_ledger_entries() -> list[LedgerEntry]:
    return get_entries()


@app.get("/api/ledger/verify", response_model=ChainVerifyResponse)
def get_ledger_verify() -> ChainVerifyResponse:
    return get_chain_status()


class TamperPreviewRequest(BaseModel):
    index: int
    new_amount_paise: int


@app.post("/api/ledger/tamper-preview", response_model=TamperPreviewResponse)
def post_ledger_tamper_preview(req: TamperPreviewRequest) -> TamperPreviewResponse:
    return tamper_preview(req.index, req.new_amount_paise)


@app.get("/api/eval/summary", response_model=EvalSummary)
def get_eval_summary() -> EvalSummary:
    try:
        return load_eval_summary()
    except EvalSummaryUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/status/summary", response_model=StatusSummary)
def get_status() -> StatusSummary:
    return get_status_summary()
