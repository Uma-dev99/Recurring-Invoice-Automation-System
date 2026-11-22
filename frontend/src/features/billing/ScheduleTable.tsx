import { Link } from "react-router";

import type { BillingPeriod } from "@/api/billing";
import type { Invoice } from "@/api/invoices";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { PERIOD_STATUS_LABEL, PERIOD_STATUS_TONE } from "@/features/billing/labels";
import { INVOICE_STATUS_LABEL, INVOICE_STATUS_TONE } from "@/features/invoices/labels";
import { cn } from "@/utils/cn";
import { formatDay, formatMoney, todayIsoDay } from "@/utils/format";

/**
 * An agreement's months, one row each.
 *
 * The "Next" / "Due now" / "Deadline passed" hints use the viewer's own date and are
 * for orientation only; the backend's billing-time-zone "today" decides what is billed.
 * ISO dates ("2027-01-31") compare correctly as plain text, so no Date objects needed.
 */
export function ScheduleTable({
  periods,
  highlightFrom,
  invoicesByPeriod,
}: {
  periods: BillingPeriod[];
  highlightFrom?: number;
  /** The invoice of each month that has one (by period id), to link to it. */
  invoicesByPeriod?: Map<string, Invoice>;
}) {
  const today = todayIsoDay();
  const next = periods.find((p) => p.status === "SCHEDULED" && p.period_end >= today);

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
          <tr>
            <th scope="col" className="px-4 py-3">Month</th>
            <th scope="col" className="px-4 py-3">Period</th>
            <th scope="col" className="px-4 py-3 text-right">Amount</th>
            <th scope="col" className="px-4 py-3">Status</th>
            {invoicesByPeriod && <th scope="col" className="px-4 py-3">Invoice</th>}
            <th scope="col" className="px-4 py-3">
              <span className="sr-only">Notes</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {periods.map((period) => {
            const isNext = period.id === next?.id;
            const preview =
              highlightFrom !== undefined && period.status === "SCHEDULED" && period.cycle_number >= highlightFrom;
            return (
              <tr
                key={period.id}
                className={cn(isNext && "bg-sky-50/60", preview && "bg-amber-50", period.status === "CANCELLED" && "text-slate-400")}
              >
                <td className="px-4 py-2.5 tabular-nums text-slate-500">{period.cycle_number}</td>
                <td className="px-4 py-2.5 whitespace-nowrap tabular-nums">
                  {formatDay(period.period_start)} – {formatDay(period.period_end)}
                </td>
                <td className="px-4 py-2.5 text-right whitespace-nowrap tabular-nums">
                  {formatMoney(period.amount, period.currency)}
                </td>
                <td className="px-4 py-2.5">
                  <StatusBadge tone={PERIOD_STATUS_TONE[period.status]}>{PERIOD_STATUS_LABEL[period.status]}</StatusBadge>
                </td>
                {invoicesByPeriod && (
                  <td className="px-4 py-2.5 whitespace-nowrap">
                    <InvoiceCell invoice={invoicesByPeriod.get(period.id)} />
                  </td>
                )}
                <td className="px-4 py-2.5 text-xs whitespace-nowrap">
                  <PeriodNote period={period} isNext={isNext} today={today} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function InvoiceCell({ invoice }: { invoice: Invoice | undefined }) {
  if (!invoice) return <span className="text-slate-300">—</span>;
  return (
    <Link to={`/invoices/${invoice.id}`} className="inline-flex items-center gap-2 hover:underline">
      <StatusBadge tone={INVOICE_STATUS_TONE[invoice.status]}>{INVOICE_STATUS_LABEL[invoice.status]}</StatusBadge>
      <span className="font-mono text-xs text-slate-500">{invoice.external_invoice_id || invoice.merchant_reference}</span>
    </Link>
  );
}

function PeriodNote({ period, isNext, today }: { period: BillingPeriod; isNext: boolean; today: string }) {
  if (period.status !== "SCHEDULED") return null;
  if (period.period_end < today) {
    // Riverty no longer accepts an invoice for this month (Phase 8 alerts on these).
    return <span className="font-medium text-red-700">Deadline passed</span>;
  }
  if (period.period_start <= today) {
    return <span className="font-medium text-sky-800">Due now · invoice by {formatDay(period.period_end)}</span>;
  }
  if (isNext) return <span className="text-sky-800">Next to bill</span>;
  return null;
}
