interface SortHeaderProps {
  label: string;
  /** Backend ordering field, e.g. "name"; "-name" is the descending version. */
  field: string;
  /** Current ordering from the URL; undefined means the list's default. */
  ordering: string | undefined;
  defaultOrdering: string;
  /** Receives the new ordering, or undefined when it equals the default (clean URL). */
  onSort: (ordering: string | undefined) => void;
}

/** A table column header that sorts by `field`; clicking again flips the direction. */
export function SortHeader({ label, field, ordering, defaultOrdering, onSort }: SortHeaderProps) {
  const current = ordering ?? defaultOrdering;
  const active = current === field || current === `-${field}`;
  const descending = current === `-${field}`;
  const next = active && !descending ? `-${field}` : field;

  return (
    <th scope="col" className="px-4 py-3" aria-sort={active ? (descending ? "descending" : "ascending") : "none"}>
      <button
        type="button"
        onClick={() => onSort(next === defaultOrdering ? undefined : next)}
        className="inline-flex items-center gap-1 uppercase tracking-wide hover:text-slate-900"
      >
        {label}
        <span aria-hidden="true" className={active ? "text-slate-900" : "text-slate-300"}>
          {active && descending ? "↓" : "↑"}
        </span>
      </button>
    </th>
  );
}
