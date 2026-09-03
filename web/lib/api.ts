// Typed fetch wrappers over the FastAPI backend (api/main.py). Shapes are
// hand-mirrored to contracts/models.py and api/attacks.py -- there is no
// shared codegen in the locked stack (docs/MASTER.md section 2), so these
// types are kept in lockstep by hand, on purpose, rather than inferred.

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export type ActionType = "create_order" | "capture" | "refund";
export type Window = "day" | "month";
export type Verdict = "safe" | "violation" | "error";

export interface PolicyIR {
  per_txn_cap_paise: number | null;
  window_cap_paise: number | null;
  window: Window | null;
  allowed_categories: string[] | null;
  blocked_categories: string[];
  max_txn_count: number | null;
  refund_bounded_by_capture: true;
  require_human_above_paise: number | null;
}

export interface Action {
  action_id: string;
  action_type: ActionType;
  order_id: string;
  amount_paise: number;
  category: string | null;
  occurred_at: string;
}

export interface CounterexampleStep {
  step_index: number;
  action_type: ActionType;
  order_id: string;
  amount_paise: number;
  category: string | null;
}

export interface Counterexample {
  violated_property: string;
  trace: CounterexampleStep[];
  violation_step_index: number;
  explanation: string | null;
}

// VerificationResult always carries verdict and horizon together -- there is
// no variant of this type that has one without the other. See VerdictBadge.
export interface VerificationResult {
  verdict: Verdict;
  properties_checked: string[];
  horizon: number;
  counterexample: Counterexample | null;
  latency_ms: number;
  error_message: string | null;
}

export interface ScenarioSummary {
  scenario_id: string;
  class_label: string;
  mandate_text: string;
  action_count: number;
}

export interface AttackStep {
  step_index: number;
  action: Action;
  poisoned_text: string | null;
  allowed: boolean;
  verification: VerificationResult;
}

export interface AttackRunResult {
  scenario_id: string;
  mandate_text: string;
  policy: PolicyIR;
  steps: AttackStep[];
  blocked_at_step: number | null;
}

class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(body || res.statusText, res.status);
  }
  return res.json() as Promise<T>;
}

export function fetchAttackScenarios(): Promise<ScenarioSummary[]> {
  return request<ScenarioSummary[]>("/api/attack/scenarios");
}

export function runAttackScenario(scenarioId: string): Promise<AttackRunResult> {
  return request<AttackRunResult>(`/api/attack/run/${encodeURIComponent(scenarioId)}`, {
    method: "POST",
  });
}

export interface ParseResponse {
  status: "ok" | "ambiguous";
  policy: PolicyIR | null;
  message: string | null;
}

export function parseMandate(text: string): Promise<ParseResponse> {
  return request<ParseResponse>("/api/mandate/parse", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
}

export function activateMandate(policy: PolicyIR, horizon = 8): Promise<VerificationResult> {
  return request<VerificationResult>("/api/mandate/activate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ policy, horizon }),
  });
}

export type GuardName = "naive" | "sound";

export function verifyProof(policy: PolicyIR, guard: GuardName, horizon = 8): Promise<VerificationResult> {
  return request<VerificationResult>("/api/proof/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ policy, guard, horizon }),
  });
}

export { ApiError };
