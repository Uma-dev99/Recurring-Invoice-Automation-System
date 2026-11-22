import { useState } from "react";
import { Link } from "react-router";

import type { AttentionSummary } from "@/api/attention";
import { ApiError } from "@/api/client";
import type { InvoiceListParams } from "@/api/invoices";
import { ErrorState } from "@/components/ui/ErrorState";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { Spinner } from "@/components/ui/Spinner";
import {
  useAttentionSummary,
  useFailedEvents,
  useInvoices,
  useMissedPeriodAction,
  useMissedPeriods,
  useRequeueFailedEvent,
} from "@/features/invoices/hooks";
import { InvoiceTable } from "@/features/invoices/InvoiceTable";
import { oneOf, positiveInt, useListSearchParams } from "@/hooks/useListUrlState";
import { cn } from "@/utils/cn";
import { formatDay, formatMoney, formatTimestamp } from "@/utils/format";

type TabKey = "needs-attention" | "rejected" | "unknown" | "stuck" | "missed" | "failed" | "retrying";

interface Tab {
  key: TabKey;
  label: string;
  count: (s: AttentionSummary) => number;
  description: string;
  invoices?: InvoiceListParams;
  /** Being handled automatically: shown for information, not counted as needing action. */
  informational?: boolean;
}

const TABS: Tab[] = [
  {
    key: "needs-attention",
    label: "Needs attention",
    count: (s) => s.needs_attention,
    description: "Automatic handling ran out of options. Open each invoice to retry, confirm or cancel it.",
    invoices: { status: "NEEDS_ATTENTION" },
  },
  {
    key: "rejected",
    label: "Rejected",
    count: (s) => s.rejected,
    description: "Riverty refused these. Fix the data (usually the customer's details), then retry.",
    invoices: { status: "REJECTED" },
  },
  {
    key: "unknown",
    label: "Unknown outcome",
    count: (s) => s.unknown,
    description:
      "Sent, but no clear answer. The system checks with Riverty every 15 minutes; act only if you know the answer.",
    invoices: { status: "UNKNOWN" },
  },
  {
    key: "stuck",
    label: "Stuck",
    count: (s) => s.stuck,
    description: "Should have been sent by now. Usually means background jobs are stopped: check System health.",
    invoices: { stuck: true },
  },
  {
    key: "missed",
    label: "Missed months",
    count: (s) => s.missed_periods,
    description: "Months of active agreements that ended without an invoice. Invoice them now or skip them.",
  },
  {
    key: "failed",
    label: "Failed background jobs",
    count: (s) => s.failed_events,
    description: "Background work that gave up after repeated errors. Fix the cause, then requeue.",
  },
  {
    key: "retrying",
    label: "Retrying",
    count: (s) => s.retry_scheduled,
    description: "Temporary problems being retried automatically. Nothing to do unless they end up here again.",
    invoices: { status: "RETRY_SCHEDULED" },
    informational: true,
  },
];

export function JobsPage() {
  const [searchParams, updateParams] = useListSearchParams();
  const tabKey = oneOf(searchParams.get("tab"), TABS.map((t) => t.key)) ?? "needs-attention";
  const page = positiveInt(searchParams.get("page"));
  const tab = TABS.find((t) => t.key === tabKey)!;
  const { data: summary } = useAttentionSummary();

  return (
    <>
      <PageHeader
        title="Failed / pending jobs"
        description={
          summary
            ? summary.total === 0
              ? "Nothing needs a person right now. This page updates automatically."
              : `${summary.total} ${summary.total === 1 ? "item needs" : "items need"} a person. This page updates automatically.`
            : "Everything the system couldn't finish on its own."
        }
      />

      <nav className="mb-4 flex flex-wrap gap-2" aria-label="Job categories">
        {TABS.map((t) => {
          const count = summary ? t.count(summary) : undefined;
          const active = t.key === tabKey;
          return (
            <button
              key={t.key}
              type="button"
              onClick={() => updateParams({ tab: t.key === "needs-attention" ? undefined : t.key })}
              aria-current={active ? "page" : undefined}
              className={cn(
                "inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm font-medium",
                active ? "border-slate-900 bg-slate-900 text-white" : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
              )}
            >
              {t.label}
              {count !== undefined && (
                <span
                  className={cn(
                    "rounded-full px-1.5 text-xs tabular-nums",
                    active
                      ? "bg-white/20"
                      : count > 0 && !t.informational
                        ? "bg-red-100 text-red-800"
                        : "bg-slate-100 text-slate-600",
                  )}
                >
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      <p className="mb-3 text-sm text-slate-600">{tab.description}</p>

      <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
        {tab.invoices ? (
          <InvoicesTab key={tab.key} params={{ ...tab.invoices, page }} onPage={(p) => updateParams({ page: pageParam(p) })} />
        ) : tab.key === "missed" ? (
          <MissedMonthsTab page={page} onPage={(p) => updateParams({ page: pageParam(p) })} />
        ) : (
          <FailedEventsTab page={page} onPage={(p) => updateParams({ page: pageParam(p) })} />
        )}
      </div>
    </>
  );
}

function pageParam(page: number): string | undefined {
  return page > 1 ? String(page) : undefined;
}

function Empty() {
  return <p className="p-10 text-center text-sm text-slate-500">Nothing here.</p>;
}

function InvoicesTab({ params, onPage }: { params: InvoiceListParams; onPage: (page: number) => void }) {
  const { data, isPending, isError, refetch, isFetching } = useInvoices(params);
  if (isPending) return <div className="p-8"><Spinner label="Loading" /></div>;
  if (isError) return <div className="p-4"><ErrorState message="Could not load these invoices." onRetry={() => refetch()} /></div>;
  if (data.results.length === 0) return <Empty />;
  return (
    <>
      <InvoiceTable invoices={data.results} showProblem />
      <Pagination page={data.page} totalPages={data.total_pages} count={data.count} isFetching={isFetching} onPageChange={onPage} />
    </>
  );
}

function MissedMonthsTab({ page, onPage }: { page: number; onPage: (page: number) => void }) {
  const { data, isPending, isError, refetch, isFetching } = useMissedPeriods(page);
  const action = useMissedPeriodAction();

  if (isPending) return <div className="p-8"><Spinner label="Loading" /></div>;
  if (isError) return <div className="p-4"><ErrorState message="Could not load missed months." onRetry={() => refetch()} /></div>;
  if (data.results.length === 0) return <Empty />;
  return (
    <>
      <ul className="divide-y divide-slate-100">
        {data.results.map((period) => (
          <li key={period.id} className="flex flex-wrap items-start justify-between gap-4 px-4 py-3 text-sm">
            <div>
              <div className="font-medium text-slate-900">
                {period.customer.name} ·{" "}
                <Link to={`/agreements/${period.agreement.id}`} className="hover:underline">
                  {period.agreement.description}
                </Link>
              </div>
              <div className="text-slate-600 tabular-nums">
                Month {period.cycle_number}: {formatDay(period.period_start)} – {formatDay(period.period_end)} ·{" "}
                {formatMoney(period.amount, period.currency)}
              </div>
            </div>
            <ReasonAction
              actions={[
                { label: "Invoice now", run: (reason) => action.mutateAsync({ id: period.id, action: "invoice-now", reason }) },
                { label: "Skip month", danger: true, run: (reason) => action.mutateAsync({ id: period.id, action: "skip", reason }) },
              ]}
            />
          </li>
        ))}
      </ul>
      <Pagination page={data.page} totalPages={data.total_pages} count={data.count} isFetching={isFetching} onPageChange={onPage} />
    </>
  );
}

function FailedEventsTab({ page, onPage }: { page: number; onPage: (page: number) => void }) {
  const { data, isPending, isError, refetch, isFetching } = useFailedEvents(page);
  const requeue = useRequeueFailedEvent();

  if (isPending) return <div className="p-8"><Spinner label="Loading" /></div>;
  if (isError) return <div className="p-4"><ErrorState message="Could not load failed jobs." onRetry={() => refetch()} /></div>;
  if (data.results.length === 0) return <Empty />;
  return (
    <>
      <ul className="divide-y divide-slate-100">
        {data.results.map((event) => (
          <li key={event.id} className="flex flex-wrap items-start justify-between gap-4 px-4 py-3 text-sm">
            <div className="min-w-0 flex-1">
              <div className="font-mono text-xs font-medium text-slate-900">{event.event_type}</div>
              <div className="text-xs text-slate-500">
                Created {formatTimestamp(event.created_at)} · gave up after {event.attempts} attempts
              </div>
              <pre className="mt-1 overflow-x-auto whitespace-pre-wrap rounded bg-slate-50 p-2 text-xs text-red-800">
                {event.last_error || "No error recorded."}
              </pre>
            </div>
            <ReasonAction actions={[{ label: "Requeue", run: (reason) => requeue.mutateAsync({ id: event.id, reason }) }]} />
          </li>
        ))}
      </ul>
      <Pagination page={data.page} totalPages={data.total_pages} count={data.count} isFetching={isFetching} onPageChange={onPage} />
    </>
  );
}

/** One or more buttons that each ask for a reason before running (kept in the audit log). */
function ReasonAction({
  actions,
}: {
  actions: { label: string; danger?: boolean; run: (reason: string) => Promise<unknown> }[];
}) {
  const [chosen, setChosen] = useState<number | null>(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  if (chosen === null) {
    return (
      <div className="flex gap-2">
        {actions.map((action, index) => (
          <button
            key={action.label}
            type="button"
            onClick={() => setChosen(index)}
            className={
              action.danger
                ? "rounded-md border border-red-300 bg-white px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-50"
                : "rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
            }
          >
            {action.label}
          </button>
        ))}
      </div>
    );
  }

  const action = actions[chosen];
  const ready = reason.trim().length >= 5;
  return (
    <form
      className="w-full max-w-sm space-y-2 sm:w-auto"
      onSubmit={async (event) => {
        event.preventDefault();
        if (!ready) return;
        setPending(true);
        setError(null);
        try {
          await action.run(reason.trim());
          setChosen(null);
          setReason("");
        } catch (err) {
          setError(err instanceof ApiError ? (err.fieldErrors.reason?.[0] ?? err.message) : "Something went wrong.");
        } finally {
          setPending(false);
        }
      }}
    >
      <label className="block text-xs text-slate-600">
        {action.label}: reason (kept in the audit log)
        <input
          autoFocus
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          className="mt-1 block w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
        />
      </label>
      {error && <p className="text-xs text-red-600">{error}</p>}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={!ready || pending}
          className={`rounded-md px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50 ${
            action.danger ? "bg-red-600 hover:bg-red-700" : "bg-slate-900 hover:bg-slate-800"
          }`}
        >
          {pending ? "Working…" : action.label}
        </button>
        <button
          type="button"
          onClick={() => setChosen(null)}
          className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
        >
          Back
        </button>
      </div>
    </form>
  );
}
