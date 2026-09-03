"use client";

// The ambient proof-state every surface can set and every surface (via
// ProofStateBackground) can read, regardless of which one is focused --
// docs/DESIGN.md's "current proof state is ambient in the background at
// all times." Defaults to "safe": nothing has been checked yet, which is
// the closest honest reading of "nothing can go wrong here" for an
// untouched dashboard. Only a real verdict (not a Ledger tamper *preview*,
// which is hypothetical by construction) is allowed to flip this.

import { createContext, useContext, useState, ReactNode } from "react";

export type ProofState = "safe" | "violation";

interface ProofStateContextValue {
  state: ProofState;
  setState: (s: ProofState) => void;
}

const ProofStateContext = createContext<ProofStateContextValue | null>(null);

export function ProofStateProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<ProofState>("safe");
  return <ProofStateContext.Provider value={{ state, setState }}>{children}</ProofStateContext.Provider>;
}

export function useProofState(): ProofStateContextValue {
  const ctx = useContext(ProofStateContext);
  if (!ctx) throw new Error("useProofState must be used within a ProofStateProvider");
  return ctx;
}
