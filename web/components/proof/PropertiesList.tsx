// Renders properties_checked entries verbatim -- including qualified ones
// like "P2[window=month,horizon-cumulative]" (ADR-0010). The qualifier is
// there specifically so the calendar-semantics caveat travels with the
// verdict; this component must never strip or reformat it away.
interface PropertiesListProps {
  properties: string[];
}

export function PropertiesList({ properties }: PropertiesListProps) {
  if (properties.length === 0) {
    return <p className="text-xs opacity-60">no properties applied by this policy</p>;
  }
  return (
    <ul className="flex flex-wrap gap-2">
      {properties.map((p) => (
        <li key={p} className="rounded-full border border-black/10 bg-black/5 px-2.5 py-1 font-mono text-xs">
          {p}
        </li>
      ))}
    </ul>
  );
}
