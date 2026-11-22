import { Link } from "react-router";

import type { Customer } from "@/api/customers";
import { ErrorState } from "@/components/ui/ErrorState";
import { Spinner } from "@/components/ui/Spinner";
import { AgreementsTable } from "@/features/agreements/AgreementsTable";
import { useAgreements } from "@/features/agreements/hooks";

const PANEL_LIMIT = 20;

/** The "Agreements" section on a customer's page. */
export function CustomerAgreementsPanel({ customer }: { customer: Customer }) {
  const { data, isPending, isError, refetch } = useAgreements({ customer: customer.id, page_size: PANEL_LIMIT });

  return (
    <section className="mt-6 max-w-5xl rounded-lg border border-slate-200 bg-white" aria-labelledby="agreements-title">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
        <h2 id="agreements-title" className="text-sm font-semibold text-slate-900">
          Agreements
        </h2>
        {customer.status === "ACTIVE" ? (
          <Link
            to={`/agreements/new?customer=${customer.id}`}
            className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800"
          >
            New agreement
          </Link>
        ) : (
          <span className="text-xs text-slate-500">Reactivate the customer to add agreements.</span>
        )}
      </div>

      {isPending ? (
        <div className="p-4">
          <Spinner label="Loading agreements" />
        </div>
      ) : isError ? (
        <div className="p-4">
          <ErrorState message="Could not load agreements." onRetry={() => refetch()} />
        </div>
      ) : data.results.length === 0 ? (
        <p className="px-4 py-6 text-center text-sm text-slate-500">No agreements yet.</p>
      ) : (
        <>
          <AgreementsTable agreements={data.results} showCustomer={false} />
          {data.count > PANEL_LIMIT && (
            <div className="border-t border-slate-200 px-4 py-3 text-sm">
              <Link to={`/agreements?customer=${customer.id}`} className="font-medium text-slate-700 underline underline-offset-2">
                View all {data.count} agreements
              </Link>
            </div>
          )}
        </>
      )}
    </section>
  );
}
