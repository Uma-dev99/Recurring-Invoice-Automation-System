import { useEffect } from "react";

import { ApiError } from "@/api/client";
import type { InvoiceListParams, InvoiceOrdering } from "@/api/invoices";
import { ErrorState } from "@/components/ui/ErrorState";
import { FilterSelect } from "@/components/ui/FilterSelect";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { SortHeader } from "@/components/ui/SortHeader";
import { Spinner } from "@/components/ui/Spinner";
import { useInvoices } from "@/features/invoices/hooks";
import { InvoiceTable } from "@/features/invoices/InvoiceTable";
import { INVOICE_STATUS_LABEL, INVOICE_STATUSES } from "@/features/invoices/labels";
import { oneOf, positiveInt, useDebouncedUrlSearch, useListSearchParams } from "@/hooks/useListUrlState";

const ORDERINGS: InvoiceOrdering[] = ["created_at", "-created_at", "period_start", "-period_start"];
const DEFAULT_ORDERING: InvoiceOrdering = "-created_at";

function readParams(searchParams: URLSearchParams): InvoiceListParams & { page: number } {
  return {
    page: positiveInt(searchParams.get("page")),
    status: oneOf(searchParams.get("status"), INVOICE_STATUSES),
    search: searchParams.get("search") || undefined,
    ordering: oneOf(searchParams.get("ordering"), ORDERINGS),
  };
}

export function InvoicesPage() {
  const [searchParams, updateParams] = useListSearchParams();
  const params = readParams(searchParams);
  const { data, isPending, isError, error, isFetching, refetch } = useInvoices(params);

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
  const hasFilters = Boolean(params.search || params.status);

  return (
    <>
      <PageHeader
        title="Invoices"
        description="One invoice per billing month, sent to Riverty by the billing run. Updates automatically."
      />

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="min-w-0 flex-1 basis-64">
          <label htmlFor="invoice-search" className="block text-xs font-medium text-slate-600">
            Search
          </label>
          <input
            id="invoice-search"
            type="search"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder="Reference, Riverty number, agreement or customer"
            className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
          />
        </div>
        <FilterSelect
          id="invoice-status"
          label="Status"
          value={params.status}
          options={INVOICE_STATUSES.map((s) => ({ value: s, label: INVOICE_STATUS_LABEL[s] }))}
          onChange={(status) => updateParams({ status })}
        />
      </div>

      <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
        {isPending || pageOutOfRange ? (
          <div className="p-8">
            <Spinner label="Loading invoices" />
          </div>
        ) : isError ? (
          <div className="p-4">
            <ErrorState message="Could not load invoices." onRetry={() => refetch()} />
          </div>
        ) : data.results.length === 0 ? (
          <div className="p-10 text-center">
            <p className="text-sm font-medium text-slate-700">
              {hasFilters ? "No invoices match these filters." : "No invoices yet."}
            </p>
            <p className="mt-1 text-sm text-slate-500">
              {hasFilters
                ? "Try a different search or clear the filters."
                : "Invoices appear when a billing month starts and the billing run picks it up."}
            </p>
          </div>
        ) : (
          <>
            <InvoiceTable
              invoices={data.results}
              headers={{
                month: <SortHeader label="Month" field="period_start" {...sortProps} />,
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
