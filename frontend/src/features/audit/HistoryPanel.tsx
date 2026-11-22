import { Link } from "react-router";

import { ErrorState } from "@/components/ui/ErrorState";
import { Spinner } from "@/components/ui/Spinner";
import { AuditEntryList } from "@/features/audit/AuditEntryList";
import { useAuditLogs } from "@/features/audit/hooks";

const LIMIT = 20;

/**
 * "What happened to this record, and who did it", read from the audit log.
 * entityType is the backend model label, e.g. "agreements.billingagreement".
 */
export function HistoryPanel({ entityType, entityId }: { entityType: string; entityId: string }) {
  const { data, isPending, isError, refetch } = useAuditLogs({
    entity_type: entityType,
    entity_id: entityId,
    page_size: LIMIT,
  });

  return (
    <section className="mt-6 max-w-4xl rounded-lg border border-slate-200 bg-white" aria-labelledby={`history-${entityId}`}>
      <h2 id={`history-${entityId}`} className="border-b border-slate-200 px-4 py-3 text-sm font-semibold text-slate-900">
        History
      </h2>
      {isPending ? (
        <div className="p-4">
          <Spinner label="Loading history" />
        </div>
      ) : isError ? (
        <div className="p-4">
          <ErrorState message="Could not load the history." onRetry={() => refetch()} />
        </div>
      ) : data.results.length === 0 ? (
        <p className="px-4 py-6 text-center text-sm text-slate-500">No recorded changes.</p>
      ) : (
        <>
          <AuditEntryList entries={data.results} showRecord={false} />
          {data.count > LIMIT && (
            <div className="border-t border-slate-200 px-4 py-3 text-sm">
              <Link
                to={`/audit-logs?entity_id=${entityId}`}
                className="font-medium text-slate-700 underline underline-offset-2"
              >
                See all {data.count} entries
              </Link>
            </div>
          )}
        </>
      )}
    </section>
  );
}
