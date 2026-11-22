import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";

import { fetchHealth, type WorkerStatus } from "@/api/health";
import { queryKeys } from "@/api/queryKeys";
import { KpiCard } from "@/components/ui/KpiCard";
import { PageHeader } from "@/components/ui/PageHeader";
import { Spinner } from "@/components/ui/Spinner";
import { StatusBadge, type StatusTone } from "@/components/ui/StatusBadge";
import { useAttentionSummary } from "@/features/invoices/hooks";

/**
 * Dashboard shell. KPI values stay empty ("—") until the backend computes them
 * (Phase 9): the frontend never invents or calculates financial figures itself.
 */
export function DashboardPage() {
  const { data: attention } = useAttentionSummary();

  return (
    <>
      <PageHeader title="Dashboard" description="Billing operations overview." />

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Key metrics">
        <KpiCard label="Active agreements" value={null} hint="Available in Phase 9" />
        <KpiCard label="Invoices due this month" value={null} hint="Available in Phase 9" />
        <KpiCard label="Accepted by Riverty" value={null} hint="Available in Phase 9" />
        <Link to="/jobs" className="block rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-500">
          <KpiCard
            label="Needs attention"
            value={attention ? attention.total : null}
            hint={attention && attention.total > 0 ? "Open Failed / pending jobs" : "Nothing to do"}
          />
        </Link>
      </section>

      <section className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="rounded-lg border border-slate-200 bg-white p-4 lg:col-span-2">
          <h2 className="text-sm font-semibold text-slate-900">Operational alerts</h2>
          <p className="mt-6 text-center text-sm text-slate-500">No alerts. Alerting is added in Phase 9.</p>
        </div>
        <SystemHealthPanel />
      </section>
    </>
  );
}

const WORKER_LABEL: Record<WorkerStatus, string> = { ok: "Running", stale: "Stopped", unknown: "Not seen yet" };
const WORKER_TONE: Record<WorkerStatus, StatusTone> = { ok: "success", stale: "danger", unknown: "warning" };

function SystemHealthPanel() {
  const { data, isPending, isError, dataUpdatedAt } = useQuery({
    queryKey: queryKeys.health,
    queryFn: fetchHealth,
    refetchInterval: 30_000,
    retry: false,
  });

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-900">System health</h2>
        {isPending ? null : isError ? (
          <StatusBadge tone="danger">Unavailable</StatusBadge>
        ) : (
          <StatusBadge tone={data.status === "ok" ? "success" : "danger"}>
            {data.status === "ok" ? "Operational" : "Degraded"}
          </StatusBadge>
        )}
      </div>

      <div className="mt-4">
        {isPending && <Spinner label="Checking" />}
        {isError && <p className="text-sm text-red-700">The API is not responding or a dependency is down.</p>}
        {data && (
          <dl className="space-y-2 text-sm">
            {Object.entries(data.checks).map(([name, state]) => (
              <div key={name} className="flex justify-between">
                <dt className="capitalize text-slate-600">{name}</dt>
                <dd>
                  <StatusBadge tone={state === "ok" ? "success" : "danger"}>{state}</StatusBadge>
                </dd>
              </div>
            ))}
            <div className="flex justify-between">
              <dt className="text-slate-600" title="Background workers that send invoices, retry and reconcile">
                Background jobs
              </dt>
              <dd>
                <StatusBadge tone={WORKER_TONE[data.background.workers]}>
                  {WORKER_LABEL[data.background.workers]}
                </StatusBadge>
              </dd>
            </div>
            {data.background.workers !== "ok" && (
              <p className="text-xs text-amber-800">
                No worker has reported in the last few minutes, so invoices are not being sent. Check that the
                worker and beat containers are running.
              </p>
            )}
            <div className="flex justify-between border-t border-slate-100 pt-2 text-xs text-slate-400">
              <span>API v{data.version}</span>
              <span>Checked {new Date(dataUpdatedAt).toLocaleTimeString()}</span>
            </div>
          </dl>
        )}
      </div>
    </div>
  );
}
