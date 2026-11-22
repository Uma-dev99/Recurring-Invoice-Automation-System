import { useEffect, useState } from "react";

import { useCustomers } from "@/features/customers/hooks";

export interface PickedCustomer {
  id: string;
  name: string;
  external_customer_id: string;
}

interface CustomerPickerProps {
  value: PickedCustomer | null;
  onChange: (customer: PickedCustomer | null) => void;
  error?: string;
}

const RESULTS = 8;

/**
 * Search-as-you-type customer chooser. Only ACTIVE customers are offered, because the
 * API refuses agreements for inactive ones. A plain <select> of every customer would
 * not scale past a few hundred rows; this asks the server for the best 8 matches.
 */
export function CustomerPicker({ value, onChange, error }: CustomerPickerProps) {
  const [input, setInput] = useState("");
  const [term, setTerm] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => setTerm(input.trim()), 300);
    return () => clearTimeout(timer);
  }, [input]);

  const { data, isPending, isError } = useCustomers({
    search: term || undefined,
    status: "ACTIVE",
    page_size: RESULTS,
  });

  if (value) {
    return (
      <div className="flex items-center justify-between gap-3 rounded-md border border-slate-300 bg-slate-50 px-3 py-2 text-sm">
        <span>
          <span className="font-medium text-slate-900">{value.name}</span>
          <span className="ml-2 font-mono text-xs text-slate-500">{value.external_customer_id}</span>
        </span>
        <button
          type="button"
          onClick={() => onChange(null)}
          className="text-sm font-medium text-slate-700 underline underline-offset-2 hover:no-underline"
        >
          Change
        </button>
      </div>
    );
  }

  return (
    <div>
      <input
        id="customer-picker"
        type="search"
        value={input}
        onChange={(event) => setInput(event.target.value)}
        placeholder="Search active customers by name, id or email"
        aria-invalid={Boolean(error)}
        aria-describedby={error ? "customer-picker-error" : undefined}
        className={`block w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-1 ${
          error ? "border-red-400 focus:ring-red-500" : "border-slate-300 focus:border-slate-500 focus:ring-slate-500"
        }`}
      />
      <div className="mt-1 rounded-md border border-slate-200">
        {isPending ? (
          <p className="px-3 py-2 text-sm text-slate-500">Searching…</p>
        ) : isError ? (
          <p className="px-3 py-2 text-sm text-red-700">Could not load customers.</p>
        ) : data.results.length === 0 ? (
          <p className="px-3 py-2 text-sm text-slate-500">No active customers match.</p>
        ) : (
          <ul className="max-h-64 divide-y divide-slate-100 overflow-y-auto">
            {data.results.map((customer) => (
              <li key={customer.id}>
                <button
                  type="button"
                  onClick={() =>
                    onChange({
                      id: customer.id,
                      name: customer.name,
                      external_customer_id: customer.external_customer_id,
                    })
                  }
                  className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-slate-50 focus:bg-slate-50 focus:outline-none"
                >
                  <span className="font-medium text-slate-900">{customer.name}</span>
                  <span className="font-mono text-xs text-slate-500">{customer.external_customer_id}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      {error && (
        <p id="customer-picker-error" className="mt-1 text-xs text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}
