interface FilterSelectProps<T extends string> {
  id: string;
  label: string;
  value: T | undefined;
  options: { value: T; label: string }[];
  onChange: (value: T | undefined) => void;
  /** Text of the "no filter" option. */
  allLabel?: string;
}

/** A labelled dropdown for list filters; the empty option means "no filter". */
export function FilterSelect<T extends string>({
  id,
  label,
  value,
  options,
  onChange,
  allLabel = "All",
}: FilterSelectProps<T>) {
  return (
    <div>
      <label htmlFor={id} className="block text-xs font-medium text-slate-600">
        {label}
      </label>
      <select
        id={id}
        value={value ?? ""}
        onChange={(event) => onChange((event.target.value || undefined) as T | undefined)}
        className="mt-1 block rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
      >
        <option value="">{allLabel}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}
