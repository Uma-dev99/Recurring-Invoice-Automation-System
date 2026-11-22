import type { ReactNode } from "react";
import { Link } from "react-router";

import type { Invoice } from "@/api/invoices";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { INVOICE_STATUS_LABEL, INVOICE_STATUS_TONE } from "@/features/invoices/labels";
import { formatDay, formatMoney, formatTimestamp } from "@/utils/format";

interface InvoiceTableProps {
  invoices: Invoice[];
  /** Optional replacement header cells for sortable columns. */
  headers?: Partial<Record<"month" | "created", ReactNode>>;
  /** Show the latest problem under the status (useful on the failed-jobs screen). */
  showProblem?: boolean;
}

/** Invoice rows, shared by the Invoices page and the Failed / pending jobs screen. */
export function InvoiceTable({ invoices, headers = {}, showProblem = false }: InvoiceTableProps) {
  const th = (label: string, className = "") => (
    <th scope="col" className={`px-4 py-3 ${className}`}>
      {label}
    </th>
  );
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
          <tr>
            {th("Reference")}
            {th("Customer · agreement")}
            {headers.month ?? th("Month")}
            {th("Amount", "text-right")}
            {th("Status")}
            {th("Riverty number")}
            {headers.created ?? th("Created")}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {invoices.map((invoice) => (
            <tr key={invoice.id} className="align-top hover:bg-slate-50">
              <td className="px-4 py-3">
                <Link to={`/invoices/${invoice.id}`} className="font-mono text-xs font-medium text-slate-900 hover:underline">
                  {invoice.merchant_reference}
                </Link>
              </td>
              <td className="px-4 py-3">
                <div className="font-medium text-slate-900">{invoice.customer.name}</div>
                <Link to={`/agreements/${invoice.agreement.id}`} className="text-xs text-slate-500 hover:underline">
                  {invoice.agreement.description}
                </Link>
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-slate-600 tabular-nums">
                {invoice.period.cycle_number} · {formatDay(invoice.period.period_start)}
              </td>
              <td className="px-4 py-3 text-right whitespace-nowrap tabular-nums">
                {formatMoney(invoice.amount, invoice.currency)}
              </td>
              <td className="px-4 py-3">
                <StatusBadge tone={INVOICE_STATUS_TONE[invoice.status]}>{INVOICE_STATUS_LABEL[invoice.status]}</StatusBadge>
                {showProblem && invoice.last_error_message && (
                  <p className="mt-1 max-w-xs text-xs text-slate-600">{invoice.last_error_message}</p>
                )}
              </td>
              <td className="px-4 py-3 font-mono text-xs text-slate-600">{invoice.external_invoice_id || "—"}</td>
              <td className="px-4 py-3 whitespace-nowrap text-slate-500 tabular-nums">
                {formatTimestamp(invoice.created_at)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
