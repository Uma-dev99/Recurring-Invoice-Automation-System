import { useEffect } from "react";
import { Link } from "react-router";

import type { AgreementListParams, AgreementOrdering } from "@/api/agreements";
import { ApiError } from "@/api/client";
import { ErrorState } from "@/components/ui/ErrorState";
import { FilterSelect } from "@/components/ui/FilterSelect";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { SortHeader } from "@/components/ui/SortHeader";
import { Spinner } from "@/components/ui/Spinner";
import { AgreementsTable } from "@/features/agreements/AgreementsTable";
import { useAgreements } from "@/features/agreements/hooks";
import { AGREEMENT_STATUSES, AGREEMENT_STATUS_LABEL } from "@/features/agreements/labels";
import { useCustomer } from "@/features/customers/hooks";
import { oneOf, positiveInt, useDebouncedUrlSearch, useListSearchParams } from "@/hooks/useListUrlState";

const ORDERINGS: AgreementOrdering[] = ["created_at", "-created_at", "anchor_date", "-anchor_date", "amount", "-amount"];
const DEFAULT_ORDERING: AgreementOrdering = "-created_at";
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function readParams(searchParams: URLSearchParams): AgreementListParams & { page: number } {
  const customer = searchParams.get("customer");
  return {
    page: positiveInt(searchParams.get("page")),
    customer: customer && UUID.test(customer) ? customer : undefined,
    status: oneOf(searchParams.get("status"), AGREEMENT_STATUSES),
    search: searchParams.get("search") || undefined,
    ordering: oneOf(searchParams.get("ordering"), ORDERINGS),
  };
}

export function AgreementsPage() {
  const [searchParams, updateParams] = useListSearchParams();
  const params = readParams(searchParams);
  const { data, isPending, isError, error, isFetching, refetch } = useAgreements(params);

  const [searchInput, setSearchInput] = useDebouncedUrlSearch(params.search ?? "", (search) =>
    updateParams({ search }),
  );

  const pageOutOfRange = error instanceof ApiError && error.status === 404 && params.page > 1;
  useEffect(() => {
    if (pageOutOfRange) updateParams({ page: undefined });
  }, [pageOutOfRange]);

  const sortProps = {
    ordering: params.ordering,
    defaultOrdering: DEFAULT_ORDERING,
    onSort: (ordering: string | undefined) => updateParams({ ordering }),
  };
  const hasFilters = Boolean(params.search || params.status || params.customer);

  return (
    <>
      <PageHeader
        title="Billing agreements"
        description="What each customer pays per month, and for how long."
        actions={
          <Link
            to={params.customer ? `/agreements/new?customer=${params.customer}` : "/agreements/new"}
            className="rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800"
          >
            New agreement
          </Link>
        }
      />

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="min-w-0 flex-1 basis-64">
          <label htmlFor="agreement-search" className="block text-xs font-medium text-slate-600">
            Search
          </label>
          <input
            id="agreement-search"
            type="search"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder="Description, customer name or id"
            className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
          />
        </div>
        <FilterSelect
          id="agreement-status"
          label="Status"
          value={params.status}
          options={AGREEMENT_STATUSES.map((s) => ({ value: s, label: AGREEMENT_STATUS_LABEL[s] }))}
          onChange={(status) => updateParams({ status })}
        />
        {params.customer && (
          <CustomerFilterChip customerId={params.customer} onClear={() => updateParams({ customer: undefined })} />
        )}
      </div>

      <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
        {isPending || pageOutOfRange ? (
          <div className="p-8">
            <Spinner label="Loading agreements" />
          </div>
        ) : isError ? (
          <div className="p-4">
            <ErrorState message="Could not load agreements." onRetry={() => refetch()} />
          </div>
        ) : data.results.length === 0 ? (
          <div className="p-10 text-center">
            <p className="text-sm font-medium text-slate-700">
              {hasFilters ? "No agreements match these filters." : "No agreements yet."}
            </p>
            <p className="mt-1 text-sm text-slate-500">
              {hasFilters ? "Try a different search or clear the filters." : "Create one from a customer's page or with New agreement."}
            </p>
          </div>
        ) : (
          <>
            <AgreementsTable
              agreements={data.results}
              headers={{
                amount: <SortHeader label="Amount / month" field="amount" {...sortProps} />,
                start: <SortHeader label="First bill" field="anchor_date" {...sortProps} />,
                created: <SortHeader label="Created" field="created_at" {...sortProps} />,
              }}
            />
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

/** Shows which customer the list is filtered to (from ?customer=<id>), with a clear button. */
function CustomerFilterChip({ customerId, onClear }: { customerId: string; onClear: () => void }) {
  const { data: customer } = useCustomer(customerId);
  return (
    <div className="flex items-center gap-2 rounded-md border border-slate-300 bg-slate-50 px-3 py-2 text-sm">
      <span className="text-slate-500">Customer:</span>
      <span className="font-medium text-slate-900">{customer?.name ?? "…"}</span>
      <button
        type="button"
        onClick={onClear}
        aria-label="Clear customer filter"
        className="ml-1 rounded px-1 text-slate-500 hover:bg-slate-200 hover:text-slate-900"
      >
        ✕
      </button>
    </div>
  );
}
