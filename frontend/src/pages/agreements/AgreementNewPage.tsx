import { Link, useNavigate, useSearchParams } from "react-router";

import type { Agreement } from "@/api/agreements";
import { PageHeader } from "@/components/ui/PageHeader";
import { Spinner } from "@/components/ui/Spinner";
import { AgreementCreateForm } from "@/features/agreements/AgreementCreateForm";
import { useCustomer } from "@/features/customers/hooks";

/**
 * /agreements/new             -> choose the customer in the form
 * /agreements/new?customer=id -> customer pre-chosen (from the customer's page)
 */
export function AgreementNewPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const customerId = searchParams.get("customer");

  const backTo = customerId ? `/customers/${customerId}` : "/agreements";
  const onCreated = (agreement: Agreement) => navigate(`/agreements/${agreement.id}`, { replace: true });
  const onCancel = () => navigate(backTo);

  return (
    <>
      <Link to={backTo} className="text-sm text-slate-500 hover:text-slate-900">
        ← {customerId ? "Customer" : "Agreements"}
      </Link>
      <PageHeader title="New billing agreement" />
      <div className="max-w-3xl rounded-lg border border-slate-200 bg-white p-6">
        {customerId ? (
          <FormForCustomer customerId={customerId} onCreated={onCreated} onCancel={onCancel} />
        ) : (
          <AgreementCreateForm initialCustomer={null} onCreated={onCreated} onCancel={onCancel} />
        )}
      </div>
    </>
  );
}

/**
 * Loads the customer named in the URL, then shows the form with it pre-chosen.
 * A top-level component on purpose: a component defined INSIDE another component's body
 * is a new component type on every render, so React would remount the form (and wipe
 * what the user typed) whenever the parent re-renders.
 */
function FormForCustomer({
  customerId,
  onCreated,
  onCancel,
}: {
  customerId: string;
  onCreated: (agreement: Agreement) => void;
  onCancel: () => void;
}) {
  const { data: customer, isPending } = useCustomer(customerId);
  if (isPending) return <Spinner label="Loading customer" />;

  // An unknown or inactive customer from the URL: fall back to choosing one.
  const initial =
    customer && customer.status === "ACTIVE"
      ? { id: customer.id, name: customer.name, external_customer_id: customer.external_customer_id }
      : null;
  return <AgreementCreateForm initialCustomer={initial} onCreated={onCreated} onCancel={onCancel} />;
}
