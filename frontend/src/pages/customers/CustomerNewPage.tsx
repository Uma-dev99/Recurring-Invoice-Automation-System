import { Link, useNavigate } from "react-router";

import { PageHeader } from "@/components/ui/PageHeader";
import { CustomerForm } from "@/features/customers/CustomerForm";
import { useCreateCustomer } from "@/features/customers/hooks";
import { EMPTY_CUSTOMER_FORM } from "@/schemas/customer";

export function CustomerNewPage() {
  const navigate = useNavigate();
  const createCustomer = useCreateCustomer();

  return (
    <>
      <Link to="/customers" className="text-sm text-slate-500 hover:text-slate-900">
        ← Customers
      </Link>
      <PageHeader title="New customer" />
      <div className="max-w-3xl rounded-lg border border-slate-200 bg-white p-6">
        <CustomerForm
          mode="create"
          defaultValues={EMPTY_CUSTOMER_FORM}
          error={createCustomer.error}
          isPending={createCustomer.isPending}
          onSubmit={(values) =>
            createCustomer.mutate(values, {
              onSuccess: (customer) => navigate(`/customers/${customer.id}`, { replace: true }),
            })
          }
          onCancel={() => navigate("/customers")}
        />
      </div>
    </>
  );
}
