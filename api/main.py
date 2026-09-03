"""Thin FastAPI orchestration layer for the Phase 7 dashboard
(docs/PHASE7-PLAN.md). Every route is a direct call into an existing
module -- verifier/, rail/, policy/, ledger/ -- with no new decision
logic. CORS is open to localhost dev origins only; this is a local demo
backend, not a deployed service handling untrusted traffic.

Run with: uvicorn api.main:app --reload --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from contracts.models import PolicyIR, VerificationResult
from policy.parse import MandateParseError

from api.attacks import AttackRunResult, ScenarioNotFoundError, ScenarioSummary, list_scenarios, run_scenario
from api.mandates import ParseResponse
from api.mandates import activate as activate_mandate
from api.mandates import parse as parse_mandate_text
from api.proof import GuardName
from api.proof import verify as verify_proof

app = FastAPI(title="Bounded dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
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


class ProofVerifyRequest(BaseModel):
    policy: PolicyIR
    guard: GuardName
    horizon: int = 8


@app.post("/api/proof/verify", response_model=VerificationResult)
def post_proof_verify(req: ProofVerifyRequest) -> VerificationResult:
    return verify_proof(req.policy, req.guard, horizon=req.horizon)
