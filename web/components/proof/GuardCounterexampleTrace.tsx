import { Counterexample } from "@/lib/api";
import { paiseToRupees } from "@/lib/format";

// verify_guard's counterexample is a fundamentally different shape from
// the Attacks surface's per-action blocks (components/trace/CounterexampleTrace):
// every step here WAS admitted by the guard under test -- that's the
// entire point ("nobody wrote that attack, the solver constructed it").
// The violation is that the *sequence* breaches the invariant, or (for a
// depth-1 P1/P4 finding) that a single admitted action already does.
// Mislabeling any step here as "blocked" would misstate what was found.
// UI 2.0 (ADR-0015): same pure-black-field trace treatment as everywhere
// else -- solid cyan block at the breach point, never a translucent one.
interface GuardCounterexampleTraceProps {
  counterexample: Counterexample;
}

export function GuardCounterexampleTrace({ counterexample }: GuardCounterexampleTraceProps) {
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
        {counterexample.trace.map((step) => {
          const isBreachPoint = step.step_index === counterexample.violation_step_index;
          return (
            <li
              key={step.step_index}
              className="flex flex-wrap items-baseline gap-x-4 gap-y-1 px-4 py-3 text-xl font-bold"
              style={
                isBreachPoint
                  ? { background: "var(--violation)", color: "var(--violation-ink)", border: "3px solid var(--violation-ink)" }
                  : { border: "3px solid transparent" }
              }
            >
              <span style={{ color: isBreachPoint ? "var(--violation-ink)" : "var(--trace-muted)" }}>
                step {step.step_index}
              </span>
              <span className="uppercase">{step.action_type}</span>
              <span>{paiseToRupees(step.amount_paise)}</span>
              <span style={{ color: isBreachPoint ? "var(--violation-ink)" : "var(--trace-muted)" }}>on</span>
              <span>{step.order_id}</span>
              {step.category && (
                <span style={{ color: isBreachPoint ? "var(--violation-ink)" : "var(--trace-muted)" }}>
                  [{step.category}]
                </span>
              )}
              <span className="ml-auto text-lg font-black" style={{ color: isBreachPoint ? "var(--violation-ink)" : "var(--admitted-on-dark)" }}>
                ADMITTED
              </span>
              {isBreachPoint && <span className="text-lg font-black">← INVARIANT BREAKS HERE</span>}
            </li>
          );
        })}
      </ol>

      <div className="mt-5 pt-5 text-xl leading-snug" style={{ borderTop: "4px solid var(--violation)" }}>
        <div className="mb-2 text-2xl font-black" style={{ color: "var(--violation)" }}>
          VIOLATED: {counterexample.violated_property}
        </div>
        <p style={{ color: "var(--trace-fg)" }}>{counterexample.explanation}</p>
      </div>
    </div>
  );
}
