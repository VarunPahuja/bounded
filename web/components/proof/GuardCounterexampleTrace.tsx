import { Counterexample } from "@/lib/api";
import { paiseToRupees } from "@/lib/format";

// verify_guard's counterexample is a fundamentally different shape from
// the Attacks surface's per-action blocks (components/trace/CounterexampleTrace):
// every step here WAS admitted by the guard under test -- that's the
// entire point ("nobody wrote that attack, the solver constructed it").
// The violation is that the *sequence* breaches the invariant, or (for a
// depth-1 P1/P4 finding) that a single admitted action already does.
// Mislabeling any step here as "blocked" would misstate what was found --
// still non-negotiable per docs/DESIGN.md: monospace, maximum contrast,
// dark field, never softened by the ambient SAFE/VIOLATION mood.
interface GuardCounterexampleTraceProps {
  counterexample: Counterexample;
}

export function GuardCounterexampleTrace({ counterexample }: GuardCounterexampleTraceProps) {
  return (
    <div className="rounded-lg border border-[#222] bg-[#0a0a0c] p-5 font-mono text-[#e8e8ec]">
      <ol className="flex flex-col gap-1">
        {counterexample.trace.map((step) => {
          const isBreachPoint = step.step_index === counterexample.violation_step_index;
          return (
            <li
              key={step.step_index}
              className="flex flex-wrap items-baseline gap-x-3 gap-y-1 rounded px-3 py-2 text-base"
              style={
                isBreachPoint
                  ? { background: "rgba(95, 227, 224, 0.12)", border: "1px solid var(--violation-accent)" }
                  : { border: "1px solid transparent" }
              }
            >
              <span className="text-[#7a7a86]">step {step.step_index}</span>
              <span className="font-semibold uppercase">{step.action_type}</span>
              <span>{paiseToRupees(step.amount_paise)}</span>
              <span className="text-[#7a7a86]">on</span>
              <span>{step.order_id}</span>
              {step.category && <span className="text-[#7a7a86]">[{step.category}]</span>}
              <span className="ml-auto font-semibold text-[#5fe38f]">ADMITTED</span>
              {isBreachPoint && (
                <span className="font-semibold" style={{ color: "var(--violation-accent)" }}>
                  ← invariant breaks here
                </span>
              )}
            </li>
          );
        })}
      </ol>

      <div className="mt-4 border-t pt-4 text-base leading-relaxed" style={{ borderColor: "var(--violation-accent)" }}>
        <div className="mb-1 font-semibold" style={{ color: "var(--violation-accent)" }}>
          violated: {counterexample.violated_property}
        </div>
        <p className="text-[#c8c8d0]">{counterexample.explanation}</p>
      </div>
    </div>
  );
}
