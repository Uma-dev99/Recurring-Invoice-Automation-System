import type { ReactNode } from "react";
import { Link } from "react-router";

import type { Agreement } from "@/api/agreements";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { AGREEMENT_STATUS_LABEL, AGREEMENT_STATUS_TONE, formatCycles } from "@/features/agreements/labels";
import { formatDay, formatMoney } from "@/utils/format";

interface AgreementsTableProps {
  agreements: Agreement[];
  /** Hide the customer column (e.g. on a customer's own page). */
  showCustomer?: boolean;
  /** Optional replacement header cells for sortable columns, keyed by column. */
  headers?: Partial<Record<"start" | "amount" | "created", ReactNode>>;
}

/** The agreement rows, shared by the agreements list and the customer page panel. */
export function AgreementsTable({ agreements, showCustomer = true, headers = {} }: AgreementsTableProps) {
  const th = (label: string) => (
    <th scope="col" className="px-4 py-3">
      {label}
    </th>
  );

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
          <tr>
            {th("Description")}
            {showCustomer && th("Customer")}
            {headers.amount ?? th("Amount / month")}
            {headers.start ?? th("First bill")}
            {th("Months")}
            {th("Status")}
            {headers.created ?? th("Created")}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {agreements.map((agreement) => (
            <tr key={agreement.id} className="hover:bg-slate-50">
              <td className="px-4 py-3 font-medium">
                <Link to={`/agreements/${agreement.id}`} className="text-slate-900 hover:underline">
                  {agreement.description}
                </Link>
              </td>
              {showCustomer && (
                <td className="px-4 py-3">
                  <Link to={`/customers/${agreement.customer.id}`} className="text-slate-700 hover:underline">
                    {agreement.customer.name}
                  </Link>
                </td>
              )}
              <td className="px-4 py-3 whitespace-nowrap text-slate-900 tabular-nums">
                {formatMoney(agreement.amount, agreement.currency)}
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-slate-600 tabular-nums">
                {formatDay(agreement.anchor_date)}
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-slate-600">{formatCycles(agreement.total_cycles)}</td>
              <td className="px-4 py-3">
                <StatusBadge tone={AGREEMENT_STATUS_TONE[agreement.status]}>
                  {AGREEMENT_STATUS_LABEL[agreement.status]}
                </StatusBadge>
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-slate-500 tabular-nums">
                {new Date(agreement.created_at).toLocaleDateString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
