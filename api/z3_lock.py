"""A single process-wide lock around every call into Z3 (task brief Phase
7b regression, found while testing the auto-run changes: the Attacks and
Mandate/Proof surfaces now auto-run on mount, which means their first
render can fire concurrent requests into Z3-backed endpoints; FastAPI
dispatches synchronous endpoints to a thread pool, and Z3's Python
bindings use one shared default context that is not safe for concurrent
use across threads -- verified live: two simultaneous /api/proof/verify-
shaped calls crashed the backend process with a native access violation
inside Z3_solver_assert, not a catchable Python exception).

Every api/ call path that reaches verifier.bmc (verify_guard, verify_action,
by way of policy.activate.activate_policy, rail.interceptor.propose_action,
or api/proof.py directly) must acquire Z3_LOCK first. This is infrastructure
in api/, not a change to verifier/ itself -- the solver stays exactly as
built; this only serializes concurrent dashboard requests into it.
"""

from __future__ import annotations

import threading

Z3_LOCK = threading.Lock()
