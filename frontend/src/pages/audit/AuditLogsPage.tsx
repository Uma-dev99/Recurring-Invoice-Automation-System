import { useEffect } from "react";

import type { AuditLogParams } from "@/api/auditLogs";
import { ApiError } from "@/api/client";
import { ErrorState } from "@/components/ui/ErrorState";
import { FilterSelect } from "@/components/ui/FilterSelect";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Spinner } from "@/components/ui/Spinner";
import { AuditEntryList } from "@/features/audit/AuditEntryList";
import { actionLabel, recordName } from "@/features/audit/format";
import { useAuditFilterOptions, useAuditLogs } from "@/features/audit/hooks";
import { positiveInt, useListSearchParams } from "@/hooks/useListUrlState";

const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function readParams(searchParams: URLSearchParams): AuditLogParams & { page: number } {
  const day = (key: string) => {
    const value = searchParams.get(key);
    return value && ISO_DAY.test(value) ? value : undefined;
  };
  const entityId = searchParams.get("entity_id");
  const actor = searchParams.get("actor");
  return {
    page: positiveInt(searchParams.get("page")),
    action: searchParams.get("action") || undefined,
    entity_type: searchParams.get("entity_type") || undefined,
    entity_id: entityId && UUID.test(entityId) ? entityId : undefined,
    actor: actor === "system" || (actor && UUID.test(actor)) ? actor : undefined,
    date_from: day("date_from"),
    date_to: day("date_to"),
  };
}

/** Every recorded change, newest first, with filters kept in the URL. */
export function AuditLogsPage() {
  const [searchParams, updateParams] = useListSearchParams();
  const params = readParams(searchParams);
  const { data, isPending, isError, error, isFetching, refetch } = useAuditLogs(params);
  const { data: options } = useAuditFilterOptions();

  const pageOutOfRange = error instanceof ApiError && error.status === 404 && params.page > 1;
  useEffect(() => {
    if (pageOutOfRange) updateParams({ page: undefined });
  }, [pageOutOfRange]);

  const hasFilters = Boolean(
    params.action || params.entity_type || params.entity_id || params.actor || params.date_from || params.date_to,
  );

  return (
    <>
      <PageHeader
        title="Audit logs"
        description="Every change to customers, agreements, billing months and invoices: who, when and what. Entries can't be edited or deleted."
      />

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <FilterSelect
          id="audit-action"
          label="Action"
          value={params.action}
          options={(options?.actions ?? []).map((a) => ({ value: a, label: `${a.split(".")[0]}: ${actionLabel(a)}` }))}
          onChange={(action) => updateParams({ action })}
        />
        <FilterSelect
          id="audit-record"
          label="Record"
          value={params.entity_type}
          options={(options?.entity_types ?? []).map((t) => ({ value: t, label: recordName(t) }))}
          onChange={(entity_type) => updateParams({ entity_type })}
        />
        <FilterSelect
          id="audit-actor"
          label="Done by"
          value={params.actor === "system" ? "system" : undefined}
          allLabel="Anyone"
          options={[{ value: "system", label: "System (background jobs)" }]}
          onChange={(actor) => updateParams({ actor })}
        />
        <DateFilter id="audit-from" label="From" value={params.date_from} onChange={(v) => updateParams({ date_from: v })} />
        <DateFilter id="audit-to" label="To" value={params.date_to} onChange={(v) => updateParams({ date_to: v })} />
        {hasFilters && (
          <button
            type="button"
            onClick={() =>
              updateParams({
                action: undefined,
                entity_type: undefined,
                entity_id: undefined,
                actor: undefined,
                date_from: undefined,
                date_to: undefined,
              })
            }
            className="rounded-md px-2 py-2 text-sm font-medium text-slate-700 underline underline-offset-2"
          >
            Clear filters
          </button>
        )}
      </div>
      {params.entity_id && (
        <p className="mb-3 text-sm text-slate-600">
          Showing one record only: <span className="font-mono text-xs">{params.entity_id}</span>
        </p>
      )}

      <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
        {isPending || pageOutOfRange ? (
          <div className="p-8">
            <Spinner label="Loading audit log" />
          </div>
        ) : isError ? (
          <div className="p-4">
            <ErrorState
              message={error instanceof ApiError ? error.message : "Could not load the audit log."}
              onRetry={() => refetch()}
            />
          </div>
        ) : data.results.length === 0 ? (
          <p className="p-10 text-center text-sm text-slate-500">
            {hasFilters ? "No entries match these filters." : "Nothing recorded yet."}
          </p>
        ) : (
          <>
            <AuditEntryList entries={data.results} />
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

function DateFilter({
  id,
  label,
  value,
  onChange,
}: {
  id: string;
  label: string;
  value: string | undefined;
  onChange: (value: string | undefined) => void;
}) {
  return (
    <div>
      <label htmlFor={id} className="block text-xs font-medium text-slate-600">
        {label}
      </label>
      <input
        id={id}
        type="date"
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value || undefined)}
        className="mt-1 block rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
      />
    </div>
  );
}
