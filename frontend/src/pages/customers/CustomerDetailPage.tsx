import { type ReactNode, useState } from "react";
import { Link, useParams } from "react-router";

import { ApiError } from "@/api/client";
import type { Customer, CustomerUpdateInput } from "@/api/customers";
import { ErrorState } from "@/components/ui/ErrorState";
import { PageHeader } from "@/components/ui/PageHeader";
import { Spinner } from "@/components/ui/Spinner";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { CustomerForm } from "@/features/customers/CustomerForm";
import { useCustomer, useSetCustomerActive, useUpdateCustomer } from "@/features/customers/hooks";
import { CUSTOMER_STATUS_LABEL, CUSTOMER_STATUS_TONE, CUSTOMER_TYPE_LABEL } from "@/features/customers/labels";
import type { CustomerFormValues } from "@/schemas/customer";

export function CustomerDetailPage() {
  const { customerId = "" } = useParams();
  const { data: customer, isPending, isError, error, refetch } = useCustomer(customerId);

  if (isPending) return <Spinner label="Loading customer" />;
  if (isError) {
    if (error instanceof ApiError && error.status === 404) {
      return (
        <div className="space-y-2">
          <h1 className="text-xl font-semibold text-slate-900">Customer not found</h1>
          <Link to="/customers" className="text-sm font-medium text-slate-700 underline underline-offset-2">
            Back to customers
          </Link>
        </div>
      );
    }
    return <ErrorState message="Could not load this customer." onRetry={() => refetch()} />;
  }
  // key: a different customer id remounts the view, so edit mode and errors reset.
  return <CustomerDetail key={customer.id} customer={customer} />;
}

function CustomerDetail({ customer }: { customer: Customer }) {
  const [editing, setEditing] = useState(false);
  const updateCustomer = useUpdateCustomer(customer.id);

  const saveChanges = (values: CustomerFormValues, dirty: Partial<Record<keyof CustomerFormValues, boolean>>) => {
    // Send only the fields the user changed (PATCH). Fields someone else changed in
    // the meantime are left alone, and the audit log records exactly this edit.
    const changes: CustomerUpdateInput = {};
    for (const field of Object.keys(dirty) as (keyof CustomerFormValues)[]) {
      if (dirty[field] && field !== "external_customer_id") {
        Object.assign(changes, { [field]: values[field] });
      }
    }
    if (Object.keys(changes).length === 0) {
      setEditing(false);
      return;
    }
    updateCustomer.mutate(changes, { onSuccess: () => setEditing(false) });
  };

  return (
    <>
      <Link to="/customers" className="text-sm text-slate-500 hover:text-slate-900">
        ← Customers
      </Link>
      <PageHeader
        title={customer.name}
        description={`${CUSTOMER_TYPE_LABEL[customer.customer_type]} · ${customer.external_customer_id}`}
        actions={
          !editing && (
            <>
              <StatusAction customer={customer} />
              <button
                type="button"
                onClick={() => {
                  updateCustomer.reset();
                  setEditing(true);
                }}
                className="rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800"
              >
                Edit
              </button>
            </>
          )
        }
      />

      <div className="max-w-3xl rounded-lg border border-slate-200 bg-white p-6">
        {editing ? (
          <CustomerForm
            mode="edit"
            defaultValues={toFormValues(customer)}
            error={updateCustomer.error}
            isPending={updateCustomer.isPending}
            onSubmit={saveChanges}
            onCancel={() => setEditing(false)}
          />
        ) : (
          <CustomerDetails customer={customer} />
        )}
      </div>
    </>
  );
}

function toFormValues(customer: Customer): CustomerFormValues {
  const { external_customer_id, customer_type, name, email, phone } = customer;
  const { address_line1, address_line2, postal_code, city, country_code } = customer;
  return {
    external_customer_id,
    customer_type,
    name,
    email,
    phone,
    address_line1,
    address_line2,
    postal_code,
    city,
    country_code,
  };
}

function CustomerDetails({ customer }: { customer: Customer }) {
  const rows: [string, ReactNode][] = [
    [
      "Status",
      <StatusBadge tone={CUSTOMER_STATUS_TONE[customer.status]}>{CUSTOMER_STATUS_LABEL[customer.status]}</StatusBadge>,
    ],
    ["External customer id", <span className="font-mono text-xs">{customer.external_customer_id}</span>],
    ["Email", customer.email],
    ["Phone", customer.phone || "—"],
    [
      "Billing address",
      <span className="whitespace-pre-line">
        {[customer.address_line1, customer.address_line2, `${customer.postal_code} ${customer.city}`, customer.country_code]
          .filter(Boolean)
          .join("\n")}
      </span>,
    ],
    ["Created", new Date(customer.created_at).toLocaleString()],
    ["Last changed", new Date(customer.updated_at).toLocaleString()],
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

/**
 * Deactivate / reactivate, with a confirmation step built into the page. The server
 * decides whether the change is allowed; a refusal (422) is shown as returned.
 */
function StatusAction({ customer }: { customer: Customer }) {
  const [confirming, setConfirming] = useState(false);
  const setActive = useSetCustomerActive(customer.id);
  const deactivating = customer.status === "ACTIVE";

  const run = () =>
    setActive.mutate(!deactivating, { onSettled: () => setConfirming(false) });

  const secondary =
    "rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60";

  return (
    <div className="flex flex-col items-end gap-1">
      {confirming ? (
        <div className="flex items-center gap-2">
          <span className="text-sm text-slate-600">{deactivating ? "Deactivate this customer?" : "Reactivate?"}</span>
          <button
            type="button"
            onClick={run}
            disabled={setActive.isPending}
            className={
              deactivating
                ? "rounded-md bg-red-600 px-3 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-60"
                : "rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-60"
            }
          >
            {setActive.isPending ? "Working…" : deactivating ? "Deactivate" : "Reactivate"}
          </button>
          <button type="button" onClick={() => setConfirming(false)} disabled={setActive.isPending} className={secondary}>
            Cancel
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => {
            setActive.reset();
            setConfirming(true);
          }}
          className={secondary}
        >
          {deactivating ? "Deactivate" : "Reactivate"}
        </button>
      )}
      {setActive.error && (
        <p role="alert" className="text-xs text-red-600">
          {setActive.error instanceof ApiError ? setActive.error.message : "Could not change the status."}
        </p>
      )}
    </div>
  );
}
