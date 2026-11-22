import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router";

import { ApiError } from "@/api/client";
import type { CustomerListParams, CustomerOrdering, CustomerStatus, CustomerType } from "@/api/customers";
import { ErrorState } from "@/components/ui/ErrorState";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Spinner } from "@/components/ui/Spinner";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useCustomers } from "@/features/customers/hooks";
import { CUSTOMER_STATUS_LABEL, CUSTOMER_STATUS_TONE, CUSTOMER_TYPE_LABEL } from "@/features/customers/labels";

const STATUSES: CustomerStatus[] = ["ACTIVE", "INACTIVE"];
const TYPES: CustomerType[] = ["PERSON", "COMPANY"];
const ORDERINGS: CustomerOrdering[] = [
  "name",
  "-name",
  "external_customer_id",
  "-external_customer_id",
  "created_at",
  "-created_at",
];
const SEARCH_DEBOUNCE_MS = 300;

function oneOf<T extends string>(value: string | null, allowed: readonly T[]): T | undefined {
  return allowed.includes(value as T) ? (value as T) : undefined;
}

/**
 * The URL is the single source of truth for the list's state (?page=&search=&...).
 * Bookmarks, shared links and the back button then all show the same view. Values
 * that don't make sense (typed by hand) are ignored rather than sent to the API.
 */
function readParams(searchParams: URLSearchParams): CustomerListParams & { page: number } {
  const page = Number(searchParams.get("page"));
  return {
    page: Number.isInteger(page) && page > 0 ? page : 1,
    search: searchParams.get("search") || undefined,
    status: oneOf(searchParams.get("status"), STATUSES),
    customer_type: oneOf(searchParams.get("customer_type"), TYPES),
    ordering: oneOf(searchParams.get("ordering"), ORDERINGS),
  };
}

export function CustomersPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const params = readParams(searchParams);
  const { data, isPending, isError, error, isFetching, refetch } = useCustomers(params);

  /** Change some list params; any change other than the page itself goes back to page 1. */
  const updateParams = (changes: Partial<Record<keyof CustomerListParams, string | undefined>>) => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      for (const [key, value] of Object.entries(changes)) {
        if (value) next.set(key, value);
        else next.delete(key);
      }
      if (!("page" in changes)) next.delete("page");
      return next;
    });
  };

  // Search box: typing updates local state at once; the URL (and so the API call)
  // follows 300 ms after the last keystroke, instead of one request per letter.
  // (updateParams is recreated every render and left out of the effect dependencies
  // on purpose: only the typed text should restart the timer.)
  const urlSearch = params.search ?? "";
  const [searchInput, setSearchInput] = useState(urlSearch);
  const lastPushedSearch = useRef(urlSearch);
  useEffect(() => {
    const trimmed = searchInput.trim();
    if (trimmed === urlSearch) return;
    const timer = setTimeout(() => {
      lastPushedSearch.current = trimmed;
      updateParams({ search: trimmed || undefined });
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [searchInput, urlSearch]);

  // The URL can also change without typing: the back button, or the "Customers" link in
  // the sidebar (which clears all filters). Then the box must show the URL's value,
  // otherwise the debounce above would put the old search straight back.
  useEffect(() => {
    if (urlSearch !== lastPushedSearch.current) {
      lastPushedSearch.current = urlSearch;
      setSearchInput(urlSearch);
    }
  }, [urlSearch]);

  // A page number past the end (e.g. after a filter shrank the list) gets a 404 from
  // the API; jump back to page 1 instead of showing an error.
  const pageOutOfRange = error instanceof ApiError && error.status === 404 && params.page > 1;
  useEffect(() => {
    if (pageOutOfRange) updateParams({ page: undefined });
  }, [pageOutOfRange]);

  const hasFilters = Boolean(params.search || params.status || params.customer_type);

  return (
    <>
      <PageHeader
        title="Customers"
        description="People and companies you send invoices to."
        actions={
          <Link
            to="/customers/new"
            className="rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800"
          >
            New customer
          </Link>
        }
      />

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="min-w-0 flex-1 basis-64">
          <label htmlFor="customer-search" className="block text-xs font-medium text-slate-600">
            Search
          </label>
          <input
            id="customer-search"
            type="search"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder="Name, external id or email"
            className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
          />
        </div>
        <FilterSelect
          id="customer-status"
          label="Status"
          value={params.status}
          options={STATUSES.map((s) => ({ value: s, label: CUSTOMER_STATUS_LABEL[s] }))}
          onChange={(status) => updateParams({ status })}
        />
        <FilterSelect
          id="customer-type"
          label="Type"
          value={params.customer_type}
          options={TYPES.map((t) => ({ value: t, label: CUSTOMER_TYPE_LABEL[t] }))}
          onChange={(customer_type) => updateParams({ customer_type })}
        />
      </div>

      <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
        {isPending || pageOutOfRange ? (
          <div className="p-8">
            <Spinner label="Loading customers" />
          </div>
        ) : isError ? (
          <div className="p-4">
            <ErrorState message="Could not load customers." onRetry={() => refetch()} />
          </div>
        ) : data.results.length === 0 ? (
          <EmptyState filtered={hasFilters} />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
                  <tr>
                    <SortHeader label="Name" field="name" ordering={params.ordering} onSort={updateParams} />
                    <SortHeader
                      label="External id"
                      field="external_customer_id"
                      ordering={params.ordering}
                      onSort={updateParams}
                    />
                    <th scope="col" className="px-4 py-3">Type</th>
                    <th scope="col" className="px-4 py-3">Email</th>
                    <th scope="col" className="px-4 py-3">City</th>
                    <th scope="col" className="px-4 py-3">Status</th>
                    <SortHeader label="Created" field="created_at" ordering={params.ordering} onSort={updateParams} />
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.results.map((customer) => (
                    <tr key={customer.id} className="hover:bg-slate-50">
                      <td className="px-4 py-3 font-medium">
                        <Link to={`/customers/${customer.id}`} className="text-slate-900 hover:underline">
                          {customer.name}
                        </Link>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-slate-600">{customer.external_customer_id}</td>
                      <td className="px-4 py-3 text-slate-600">{CUSTOMER_TYPE_LABEL[customer.customer_type]}</td>
                      <td className="px-4 py-3 text-slate-600">{customer.email}</td>
                      <td className="px-4 py-3 text-slate-600">
                        {customer.city}, {customer.country_code}
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge tone={CUSTOMER_STATUS_TONE[customer.status]}>
                          {CUSTOMER_STATUS_LABEL[customer.status]}
                        </StatusBadge>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-slate-500 tabular-nums">
                        {new Date(customer.created_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              page={data.page}
              totalPages={data.total_pages}
              count={data.count}
              isFetching={isFetching}
              onPageChange={(page) => updateParams({ page: page > 1 ? String(page) : undefined })}
            />
          </>
        )}
      </div>
    </>
  );
}

function FilterSelect<T extends string>({
  id,
  label,
  value,
  options,
  onChange,
}: {
  id: string;
  label: string;
  value: T | undefined;
  options: { value: T; label: string }[];
  onChange: (value: T | undefined) => void;
}) {
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
        <option value="">All</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}

/** Column header that sorts by `field`; clicking again flips the direction. */
function SortHeader({
  label,
  field,
  ordering = "name",
  onSort,
}: {
  label: string;
  field: "name" | "external_customer_id" | "created_at";
  ordering?: CustomerOrdering;
  onSort: (changes: { ordering: string | undefined }) => void;
}) {
  const active = ordering === field || ordering === `-${field}`;
  const descending = ordering === `-${field}`;
  const next = active && !descending ? `-${field}` : field;

  return (
    <th scope="col" className="px-4 py-3" aria-sort={active ? (descending ? "descending" : "ascending") : "none"}>
      <button
        type="button"
        onClick={() => onSort({ ordering: next === "name" ? undefined : next })}
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

function EmptyState({ filtered }: { filtered: boolean }) {
  return (
    <div className="p-10 text-center">
      <p className="text-sm font-medium text-slate-700">
        {filtered ? "No customers match these filters." : "No customers yet."}
      </p>
      <p className="mt-1 text-sm text-slate-500">
        {filtered ? "Try a different search or clear the filters." : "Create the first customer to start billing."}
      </p>
    </div>
  );
}
