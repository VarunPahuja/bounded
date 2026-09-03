import { AttackStep } from "@/lib/api";
import { paiseToRupees } from "@/lib/format";

// UI 2.0 (ADR-0015): trace surfaces are unconditionally a pure black
// field with bright monospace -- this is now the default treatment, not
// an exception carved out for one component. BLOCKED gets a solid cyan
// block (never a translucent overlay -- no opacity-based hierarchy).
interface CounterexampleTraceProps {
  steps: AttackStep[];
  blockedAtStep: number | null;
}

export function CounterexampleTrace({ steps, blockedAtStep }: CounterexampleTraceProps) {
  const blockedStep = steps.find((s) => s.step_index === blockedAtStep);
  const counterexample = blockedStep?.verification.counterexample ?? null;

  return (
    <div
      className="nb-mono p-6"
      style={{
        background: "var(--trace-bg)",
        color: "var(--trace-fg)",
        border: "4px solid var(--trace-fg)",
        boxShadow: "8px 8px 0 var(--violation)",
      }}
    >
      <ol className="flex flex-col gap-2">
        {steps.map((step) => {
          const isBlocked = step.step_index === blockedAtStep;
          return (
            <li
              key={step.step_index}
              className="flex flex-wrap items-baseline gap-x-4 gap-y-1 px-4 py-3 text-xl font-bold"
              style={
                isBlocked
                  ? { background: "var(--violation)", color: "var(--violation-ink)", border: "3px solid var(--violation-ink)" }
                  : { border: "3px solid transparent" }
              }
            >
              <span style={{ color: isBlocked ? "var(--violation-ink)" : "var(--trace-muted)" }}>
                step {step.step_index}
              </span>
              <span className="uppercase">{step.action.action_type}</span>
              <span>{paiseToRupees(step.action.amount_paise)}</span>
              <span style={{ color: isBlocked ? "var(--violation-ink)" : "var(--trace-muted)" }}>on</span>
              <span>{step.action.order_id}</span>
              {step.action.category && (
                <span style={{ color: isBlocked ? "var(--violation-ink)" : "var(--trace-muted)" }}>
                  [{step.action.category}]
                </span>
              )}
              <span className="ml-auto text-2xl font-black" style={{ color: isBlocked ? "var(--violation-ink)" : "#39ff6a" }}>
                {step.allowed ? "ADMITTED" : "BLOCKED"}
              </span>
            </li>
          );
        })}
      </ol>

      {counterexample && (
        <div className="mt-5 pt-5 text-xl leading-snug" style={{ borderTop: "4px solid var(--violation)" }}>
          <div className="mb-2 text-2xl font-black" style={{ color: "var(--violation)" }}>
            VIOLATED: {counterexample.violated_property} (at scenario step {blockedAtStep})
          </div>
          {/* The solver's own explanation is a self-contained, depth-1 check against
              the account state at the moment of this one action -- its internal
              "step 1" refers to itself, not this scenario's step numbering above.
              Shown verbatim (never rewritten) with that framing made explicit. */}
          <p style={{ color: "var(--trace-fg)" }}>
            solver&apos;s explanation for this rejection: &ldquo;{counterexample.explanation}&rdquo;
          </p>
        </div>
      )}

      {blockedAtStep === null && (
        <p className="mt-5 pt-5 text-xl font-bold" style={{ borderTop: "4px solid #39ff6a", color: "#39ff6a" }}>
          every action in this sequence was admitted — no violation found.
        </p>
      )}
    </div>
  );
}
