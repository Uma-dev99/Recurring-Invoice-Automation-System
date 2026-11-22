import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";

import { fetchHealth, type WorkerStatus } from "@/api/health";
import { queryKeys } from "@/api/queryKeys";
import { KpiCard } from "@/components/ui/KpiCard";
import { PageHeader } from "@/components/ui/PageHeader";
import { Spinner } from "@/components/ui/Spinner";
import { ErrorState } from "@/components/ui/ErrorState";
import { StatusBadge, type StatusTone } from "@/components/ui/StatusBadge";
import { AuditEntryList } from "@/features/audit/AuditEntryList";
import { useAuditLogs, useDashboard } from "@/features/audit/hooks";
import { formatMoney } from "@/utils/format";

/**
 * Every figure here is computed by the backend (apps/dashboard/selectors.py) and only
 * displayed: the frontend never calculates financial numbers itself.
 */
export function DashboardPage() {
  const { data: kpis, isError } = useDashboard();
  const monthName = kpis ? monthLabel(kpis.month_start) : "This month";

  return (
    <>
      <PageHeader
        title="Dashboard"
        description={kpis ? `Billing operations overview · ${monthName}` : "Billing operations overview."}
      />
      {isError && <ErrorState message="Could not load the dashboard figures." />}

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5" aria-label="Key metrics">
        <KpiCard
          label="Active agreements"
          value={kpis?.active_agreements ?? null}
          hint={kpis ? `${kpis.paused_agreements} paused` : undefined}
        />
        <KpiCard
          label={`Scheduled in ${monthName}`}
          value={kpis ? formatMoney(kpis.month_scheduled.amount) : null}
          hint={
            kpis
              ? `${plural(kpis.month_scheduled.count, "month")} · ${kpis.month_invoiced.count} invoiced, ${kpis.month_open.count} to go`
              : undefined
          }
        />
        <KpiCard
          label="Accepted by Riverty"
          value={kpis ? formatMoney(kpis.accepted_this_month.amount) : null}
          hint={kpis ? `${plural(kpis.accepted_this_month.count, "invoice")} this month · not the same as paid` : undefined}
        />
        <KpiCard
          label={kpis ? `Next ${kpis.upcoming_days} days` : "Coming up"}
          value={kpis ? formatMoney(kpis.upcoming.amount) : null}
          hint={kpis ? `${plural(kpis.upcoming.count, "month")} start billing` : undefined}
        />
        <Link to="/jobs" className="block rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-500">
          <KpiCard
            label="Needs attention"
            value={kpis?.needs_attention ?? null}
            hint={kpis && kpis.needs_attention > 0 ? "Open Failed / pending jobs" : "Nothing to do"}
          />
        </Link>
      </section>

      <section className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <RecentActivity />
        <SystemHealthPanel />
      </section>
    </>
  );
}

function RecentActivity() {
  const { data, isPending } = useAuditLogs({ page_size: 8 });
  return (
    <div className="rounded-lg border border-slate-200 bg-white lg:col-span-2">
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-900">Recent activity</h2>
        <Link to="/audit-logs" className="text-sm font-medium text-slate-700 underline underline-offset-2">
          Audit logs
        </Link>
      </div>
      {isPending ? (
        <div className="p-4">
          <Spinner label="Loading" />
        </div>
      ) : !data || data.results.length === 0 ? (
        <p className="px-4 py-6 text-center text-sm text-slate-500">Nothing recorded yet.</p>
      ) : (
        <AuditEntryList entries={data.results} compact />
      )}
    </div>
  );
}

function plural(count: number, word: string): string {
  return `${count} ${count === 1 ? word : `${word}s`}`;
}

/** "2026-11-01" -> "November 2026" (built from parts: no time-zone shift). */
function monthLabel(isoDay: string): string {
  const [year, month] = isoDay.split("-").map(Number);
  return new Date(year, month - 1, 1).toLocaleDateString("en-GB", { month: "long", year: "numeric" });
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
