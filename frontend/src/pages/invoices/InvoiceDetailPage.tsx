import type { ReactNode } from "react";
import { Link, useParams } from "react-router";

import { ApiError } from "@/api/client";
import type { InvoiceDetail, ProcessingAttempt } from "@/api/invoices";
import { ErrorState } from "@/components/ui/ErrorState";
import { PageHeader } from "@/components/ui/PageHeader";
import { Spinner } from "@/components/ui/Spinner";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { HistoryPanel } from "@/features/audit/HistoryPanel";
import { useInvoice } from "@/features/invoices/hooks";
import { OperatorActions } from "@/features/invoices/OperatorActions";
import {
  ATTEMPT_OUTCOME_LABEL,
  ATTEMPT_OUTCOME_TONE,
  INVOICE_STATUS_EXPLANATION,
  INVOICE_STATUS_LABEL,
  INVOICE_STATUS_TONE,
} from "@/features/invoices/labels";
import { formatDay, formatMoney, formatTimestamp } from "@/utils/format";

export function InvoiceDetailPage() {
  const { invoiceId = "" } = useParams();
  const { data: invoice, isPending, isError, error, refetch } = useInvoice(invoiceId);

  if (isPending) return <Spinner label="Loading invoice" />;
  if (isError) {
    if (error instanceof ApiError && error.status === 404) {
      return (
        <div className="space-y-2">
          <h1 className="text-xl font-semibold text-slate-900">Invoice not found</h1>
          <Link to="/invoices" className="text-sm font-medium text-slate-700 underline underline-offset-2">
            Back to invoices
          </Link>
        </div>
      );
    }
    return <ErrorState message="Could not load this invoice." onRetry={() => refetch()} />;
  }

  return (
    <>
      <Link to="/invoices" className="text-sm text-slate-500 hover:text-slate-900">
        ← Invoices
      </Link>
      <PageHeader
        title={invoice.merchant_reference}
        description={`${invoice.customer.name} · ${invoice.agreement.description} · month ${invoice.period.cycle_number}`}
      />

      <div className="max-w-3xl space-y-6">
        <StatusPanel invoice={invoice} />
        <OperatorActions invoice={invoice} />
        <div className="rounded-lg border border-slate-200 bg-white p-6">
          <InvoiceFacts invoice={invoice} />
        </div>
        <Attempts attempts={invoice.attempts} />
        <HistoryPanel entityType="invoicing.invoicesubmission" entityId={invoice.id} />
      </div>
    </>
  );
}

function StatusPanel({ invoice }: { invoice: InvoiceDetail }) {
  const problem = invoice.status === "REJECTED" || invoice.status === "NEEDS_ATTENTION";
  return (
    <div
      className={`rounded-lg border p-4 text-sm ${
        problem ? "border-red-200 bg-red-50" : "border-slate-200 bg-white"
      }`}
    >
      <div className="flex flex-wrap items-center gap-3">
        <StatusBadge tone={INVOICE_STATUS_TONE[invoice.status]}>{INVOICE_STATUS_LABEL[invoice.status]}</StatusBadge>
        <p className="text-slate-700">{INVOICE_STATUS_EXPLANATION[invoice.status]}</p>
      </div>
      {invoice.last_error_message && (
        <p className={`mt-3 ${problem ? "text-red-800" : "text-slate-600"}`}>
          <span className="font-medium">Latest problem</span>
          {invoice.last_error_category && (
            <span className="ml-1 font-mono text-xs">({invoice.last_error_category})</span>
          )}
          : {invoice.last_error_message}
        </p>
      )}
      {invoice.status === "RETRY_SCHEDULED" && invoice.next_attempt_at && (
        <p className="mt-2 text-slate-600">Next attempt from {formatTimestamp(invoice.next_attempt_at)}.</p>
      )}
    </div>
  );
}

function InvoiceFacts({ invoice }: { invoice: InvoiceDetail }) {
  const rows: [string, ReactNode][] = [
    ["Amount", <span className="tabular-nums">{formatMoney(invoice.amount, invoice.currency)} (VAT included)</span>],
    [
      "Billing month",
      `Month ${invoice.period.cycle_number}: ${formatDay(invoice.period.period_start)} – ${formatDay(invoice.period.period_end)}`,
    ],
    ["Invoice deadline", formatDay(invoice.period.period_end)],
    [
      "Agreement",
      <Link to={`/agreements/${invoice.agreement.id}`} className="font-medium text-slate-900 hover:underline">
        {invoice.agreement.description}
      </Link>,
    ],
    [
      "Customer",
      <Link to={`/customers/${invoice.customer.id}`} className="font-medium text-slate-900 hover:underline">
        {invoice.customer.name}
      </Link>,
    ],
    ["Our reference", <span className="font-mono text-xs">{invoice.merchant_reference}</span>],
    ["Riverty number", <span className="font-mono text-xs">{invoice.external_invoice_id || "—"}</span>],
    ["Accepted", invoice.accepted_at ? formatTimestamp(invoice.accepted_at) : "—"],
    ["Created", formatTimestamp(invoice.created_at)],
  ];
  return (
    <dl className="divide-y divide-slate-100 text-sm">
      {rows.map(([label, value]) => (
        <div key={label} className="grid grid-cols-1 gap-1 py-3 sm:grid-cols-3 sm:gap-4">
          <dt className="font-medium text-slate-500">{label}</dt>
          <dd className="text-slate-900 sm:col-span-2">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Every call made to Riverty for this invoice: the answer to "what happened?". */
function Attempts({ attempts }: { attempts: ProcessingAttempt[] }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white" aria-labelledby="attempts-title">
      <h2 id="attempts-title" className="border-b border-slate-200 px-4 py-3 text-sm font-semibold text-slate-900">
        Attempts with Riverty
      </h2>
      {attempts.length === 0 ? (
        <p className="px-4 py-6 text-center text-sm text-slate-500">Not sent yet.</p>
      ) : (
        <ol className="divide-y divide-slate-100">
          {attempts.map((attempt) => (
            <li key={attempt.attempt_number} className="px-4 py-3 text-sm">
              <div className="flex flex-wrap items-center gap-3">
                <span className="font-medium text-slate-900">Attempt {attempt.attempt_number}</span>
                <StatusBadge tone={ATTEMPT_OUTCOME_TONE[attempt.outcome]}>{ATTEMPT_OUTCOME_LABEL[attempt.outcome]}</StatusBadge>
                <span className="text-xs text-slate-500 tabular-nums">
                  {formatTimestamp(attempt.started_at)}
                  {attempt.finished_at && ` · took ${durationSeconds(attempt.started_at, attempt.finished_at)}`}
                </span>
              </div>
              {attempt.error_message && (
                <p className="mt-1 text-slate-600">
                  {attempt.error_category && <span className="font-mono text-xs">{attempt.error_category}: </span>}
                  {attempt.error_message}
                </p>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function durationSeconds(start: string, end: string): string {
  const ms = new Date(end).getTime() - new Date(start).getTime();
  return ms < 1000 ? `${Math.max(ms, 0)} ms` : `${(ms / 1000).toFixed(1)} s`;
}
