import { useQuery } from "@tanstack/react-query";

import { fetchHealth } from "@/api/health";
import { queryKeys } from "@/api/queryKeys";
import { KpiCard } from "@/components/ui/KpiCard";
import { PageHeader } from "@/components/ui/PageHeader";
import { Spinner } from "@/components/ui/Spinner";
import { StatusBadge } from "@/components/ui/StatusBadge";

/**
 * Dashboard shell. KPI values stay empty ("—") until the backend computes them
 * (Phase 9): the frontend never invents or calculates financial figures itself.
 */
export function DashboardPage() {
  return (
    <>
      <PageHeader title="Dashboard" description="Billing operations overview." />

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Key metrics">
        <KpiCard label="Active agreements" value={null} hint="Available after Phase 3" />
        <KpiCard label="Invoices due this month" value={null} hint="Available after Phase 4" />
        <KpiCard label="Accepted by Riverty" value={null} hint="Available after Phase 6" />
        <KpiCard label="Needs attention" value={null} hint="Failed + unknown, Phase 8" />
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
