import { AttackStep } from "@/lib/api";
import { paiseToRupees } from "@/lib/format";

// Non-negotiable per docs/DESIGN.md: counterexample traces are always
// maximum-contrast monospace on a dark field, regardless of the ambient
// SAFE/VIOLATION mood elsewhere on the page. This component never reads
// the ambient proof-state and never softens its own contrast.
interface CounterexampleTraceProps {
  steps: AttackStep[];
  blockedAtStep: number | null;
}

export function CounterexampleTrace({ steps, blockedAtStep }: CounterexampleTraceProps) {
  const blockedStep = steps.find((s) => s.step_index === blockedAtStep);
  const counterexample = blockedStep?.verification.counterexample ?? null;

  return (
    <div className="rounded-lg border border-[#222] bg-[#0a0a0c] p-5 font-mono text-[#e8e8ec]">
      <ol className="flex flex-col gap-1">
        {steps.map((step) => {
          const isBlocked = step.step_index === blockedAtStep;
          return (
            <li
              key={step.step_index}
              className="flex flex-wrap items-baseline gap-x-3 gap-y-1 rounded px-3 py-2 text-base"
              style={
                isBlocked
                  ? { background: "rgba(95, 227, 224, 0.12)", border: "1px solid var(--violation-accent)" }
                  : { border: "1px solid transparent" }
              }
            >
              <span className="text-[#7a7a86]">step {step.step_index}</span>
              <span className="font-semibold uppercase">{step.action.action_type}</span>
              <span>{paiseToRupees(step.action.amount_paise)}</span>
              <span className="text-[#7a7a86]">on</span>
              <span>{step.action.order_id}</span>
              {step.action.category && <span className="text-[#7a7a86]">[{step.action.category}]</span>}
              <span
                className="ml-auto font-semibold"
                style={{ color: isBlocked ? "var(--violation-accent)" : "#5fe38f" }}
              >
                {step.allowed ? "ADMITTED" : "BLOCKED"}
              </span>
            </li>
          );
        })}
      </ol>

      {counterexample && (
        <div
          className="mt-4 border-t pt-4 text-base leading-relaxed"
          style={{ borderColor: "var(--violation-accent)" }}
        >
          <div className="mb-1 font-semibold" style={{ color: "var(--violation-accent)" }}>
            violated: {counterexample.violated_property} (at scenario step {blockedAtStep})
          </div>
          {/* The solver's own explanation is a self-contained, depth-1 check against
              the account state at the moment of this one action -- its internal
              "step 1" refers to itself, not this scenario's step numbering above.
              Shown verbatim (never rewritten) with that framing made explicit. */}
          <p className="text-[#c8c8d0]">
            solver&apos;s explanation for this rejection: &ldquo;{counterexample.explanation}&rdquo;
          </p>
        </div>
      )}

      {blockedAtStep === null && (
        <p className="mt-4 border-t border-[#222] pt-4 text-base text-[#5fe38f]">
          every action in this sequence was admitted -- no violation found.
        </p>
      )}
    </div>
  );
}
