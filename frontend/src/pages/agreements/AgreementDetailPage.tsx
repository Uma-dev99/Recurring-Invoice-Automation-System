import { zodResolver } from "@hookform/resolvers/zod";
import { type ReactNode, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useParams } from "react-router";

import type { Agreement } from "@/api/agreements";
import { ApiError } from "@/api/client";
import { ErrorState } from "@/components/ui/ErrorState";
import { PageHeader } from "@/components/ui/PageHeader";
import { Spinner } from "@/components/ui/Spinner";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ChangeAmountForm } from "@/features/agreements/ChangeAmountForm";
import {
  isVersionConflict,
  useAgreement,
  useAgreementAction,
  useAgreementPeriods,
  useChangeAgreementAmount,
  useUpdateAgreement,
} from "@/features/agreements/hooks";
import { ScheduleTable } from "@/features/billing/ScheduleTable";
import { useInvoices } from "@/features/invoices/hooks";
import { AGREEMENT_STATUS_LABEL, AGREEMENT_STATUS_TONE, formatCycles } from "@/features/agreements/labels";
import { type AgreementEditValues, agreementEditSchema } from "@/schemas/agreement";
import { formatDay, formatMoney, formatTimestamp } from "@/utils/format";

export function AgreementDetailPage() {
  const { agreementId = "" } = useParams();
  const { data: agreement, isPending, isError, error, refetch } = useAgreement(agreementId);

  if (isPending) return <Spinner label="Loading agreement" />;
  if (isError) {
    if (error instanceof ApiError && error.status === 404) {
      return (
        <div className="space-y-2">
          <h1 className="text-xl font-semibold text-slate-900">Agreement not found</h1>
          <Link to="/agreements" className="text-sm font-medium text-slate-700 underline underline-offset-2">
            Back to agreements
          </Link>
        </div>
      );
    }
    return <ErrorState message="Could not load this agreement." onRetry={() => refetch()} />;
  }
  return <AgreementDetail key={agreement.id} agreement={agreement} />;
}

function AgreementDetail({ agreement }: { agreement: Agreement }) {
  const [editing, setEditing] = useState(false);
  const update = useUpdateAgreement(agreement.id);
  const action = useAgreementAction(agreement.id);
  const changeAmount = useChangeAgreementAmount(agreement.id);
  const closed = agreement.status === "CANCELLED" || agreement.status === "COMPLETED";

  // Any write may have lost a race with someone else's change. The hooks already
  // refetched the agreement and its schedule; explain what happened.
  const conflict =
    isVersionConflict(update.error) || isVersionConflict(action.error) || isVersionConflict(changeAmount.error);
  const dismissConflict = () => {
    update.reset();
    action.reset();
    changeAmount.reset();
  };

  return (
    <>
      <Link to="/agreements" className="text-sm text-slate-500 hover:text-slate-900">
        ← Agreements
      </Link>
      <PageHeader
        title={agreement.description}
        description={`${formatMoney(agreement.amount, agreement.currency)} per month · ${agreement.customer.name}`}
        actions={
          !editing &&
          !closed && (
            <button
              type="button"
              onClick={() => {
                dismissConflict();
                setEditing(true);
              }}
              className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Edit description
            </button>
          )
        }
      />

      {conflict && (
        <div role="alert" className="mb-4 flex max-w-3xl flex-wrap items-start justify-between gap-3 rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <p>
            <span className="font-medium">Someone else changed this agreement</span> while you had it open, so your
            change was not saved. The page now shows the latest version. Check it and try again if still needed.
          </p>
          <button type="button" onClick={dismissConflict} className="font-medium underline underline-offset-2">
            OK
          </button>
        </div>
      )}

      <div className="max-w-3xl space-y-6">
        <div className="rounded-lg border border-slate-200 bg-white p-6">
          {editing ? (
            <DescriptionForm
              agreement={agreement}
              mutation={update}
              onDone={() => setEditing(false)}
            />
          ) : (
            <AgreementDetails agreement={agreement} />
          )}
        </div>

        {!closed && !editing && <LifecycleActions agreement={agreement} mutation={action} />}
      </div>

      <ScheduleSection agreement={agreement} closed={closed} mutation={changeAmount} />
    </>
  );
}

/** The month-by-month schedule, with the "change price from month N" form. */
function ScheduleSection({
  agreement,
  closed,
  mutation,
}: {
  agreement: Agreement;
  closed: boolean;
  mutation: ReturnType<typeof useChangeAgreementAmount>;
}) {
  const { data: periods, isPending, isError, refetch } = useAgreementPeriods(agreement.id);
  // The invoice of each month. 100 is the API's page-size cap; an agreement longer than
  // 100 months shows invoices for its first 100 here (the Invoices page has them all).
  const { data: invoices } = useInvoices({ agreement: agreement.id, page_size: 100, ordering: "period_start" });
  const invoicesByPeriod = useMemo(
    () => new Map((invoices?.results ?? []).map((invoice) => [invoice.period.id, invoice])),
    [invoices],
  );
  const [changing, setChanging] = useState(false);
  const [previewFrom, setPreviewFrom] = useState<number | undefined>();

  return (
    <section className="mt-6 max-w-4xl rounded-lg border border-slate-200 bg-white" aria-labelledby="schedule-title">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
        <div>
          <h2 id="schedule-title" className="text-sm font-semibold text-slate-900">
            Schedule
          </h2>
          <p className="text-xs text-slate-500">
            Each month is invoiced from its first day and must be invoiced by its last day.
          </p>
        </div>
        {!closed && !changing && periods && periods.length > 0 && (
          <button
            type="button"
            onClick={() => {
              mutation.reset();
              setChanging(true);
            }}
            className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Change price…
          </button>
        )}
      </div>

      {isPending ? (
        <div className="p-4">
          <Spinner label="Loading schedule" />
        </div>
      ) : isError ? (
        <div className="p-4">
          <ErrorState message="Could not load the schedule." onRetry={() => refetch()} />
        </div>
      ) : periods.length === 0 ? (
        <p className="px-4 py-6 text-center text-sm text-slate-500">
          No schedule yet. Run <code className="font-mono">manage.py backfill_billing_periods</code> for agreements
          created before billing periods existed.
        </p>
      ) : (
        <>
          {changing && (
            <div className="border-b border-slate-200 p-4">
              <ChangeAmountForm
                agreement={agreement}
                periods={periods}
                mutation={mutation}
                onPreview={setPreviewFrom}
                onDone={() => setChanging(false)}
              />
            </div>
          )}
          <ScheduleTable
            periods={periods}
            highlightFrom={changing ? previewFrom : undefined}
            invoicesByPeriod={invoicesByPeriod}
          />
        </>
      )}
    </section>
  );
}

function AgreementDetails({ agreement }: { agreement: Agreement }) {
  const rows: [string, ReactNode][] = [
    [
      "Status",
      <StatusBadge tone={AGREEMENT_STATUS_TONE[agreement.status]}>{AGREEMENT_STATUS_LABEL[agreement.status]}</StatusBadge>,
    ],
    [
      "Customer",
      <Link to={`/customers/${agreement.customer.id}`} className="font-medium text-slate-900 hover:underline">
        {agreement.customer.name}{" "}
        <span className="font-mono text-xs font-normal text-slate-500">{agreement.customer.external_customer_id}</span>
      </Link>,
    ],
    [
      "Current price",
      <span className="tabular-nums">
        {formatMoney(agreement.amount, agreement.currency)} per month{" "}
        <span className="text-slate-500">(VAT included)</span>
      </span>,
    ],
    ["Schedule", `${formatCycles(agreement.total_cycles)}, first bill on ${formatDay(agreement.anchor_date)}`],
    ...(agreement.cancelled_at ? [["Cancelled", formatTimestamp(agreement.cancelled_at)] as [string, ReactNode]] : []),
    ["Created", formatTimestamp(agreement.created_at)],
    ["Last changed", `${formatTimestamp(agreement.updated_at)} · version ${agreement.version}`],
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

function DescriptionForm({
  agreement,
  mutation,
  onDone,
}: {
  agreement: Agreement;
  mutation: ReturnType<typeof useUpdateAgreement>;
  onDone: () => void;
}) {
  const {
    register,
    handleSubmit,
    formState: { errors, isDirty },
  } = useForm<AgreementEditValues>({
    resolver: zodResolver(agreementEditSchema),
    defaultValues: { description: agreement.description },
  });

  const onSubmit = ({ description }: AgreementEditValues) => {
    if (!isDirty) return onDone();
    // Send the version this page was showing; the server refuses (409) if it is stale.
    // On a conflict, close the form: the user must first SEE what the other person saved,
    // otherwise pressing Save again would overwrite it with the now-current version.
    mutation.mutate(
      { version: agreement.version, description },
      { onSuccess: onDone, onError: (error) => isVersionConflict(error) && onDone() },
    );
  };

  const serverError =
    mutation.error instanceof ApiError && !isVersionConflict(mutation.error)
      ? (mutation.error.fieldErrors.description?.[0] ?? mutation.error.message)
      : null;

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
      <div>
        <label htmlFor="edit-description" className="block text-sm font-medium text-slate-700">
          Description
        </label>
        <input
          id="edit-description"
          {...register("description")}
          aria-invalid={Boolean(errors.description || serverError)}
          className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
        />
        {(errors.description || serverError) && (
          <p className="mt-1 text-xs text-red-600">{errors.description?.message ?? serverError}</p>
        )}
      </div>
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={mutation.isPending}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-60"
        >
          {mutation.isPending ? "Saving…" : "Save"}
        </button>
        <button
          type="button"
          onClick={onDone}
          disabled={mutation.isPending}
          className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

/**
 * Pause / resume / cancel. Which buttons show follows the same rules as the backend's
 * lifecycle.py, but the server stays the authority: a refusal (422) or a version
 * conflict (409) is shown as returned.
 */
function LifecycleActions({
  agreement,
  mutation,
}: {
  agreement: Agreement;
  mutation: ReturnType<typeof useAgreementAction>;
}) {
  const [confirmingCancel, setConfirmingCancel] = useState(false);
  const [reason, setReason] = useState("");
  const { version } = agreement;

  const secondary =
    "rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60";
  const error =
    mutation.error && !isVersionConflict(mutation.error)
      ? mutation.error instanceof ApiError
        ? mutation.error.message
        : "Could not change the agreement."
      : null;

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-6" aria-labelledby="lifecycle-title">
      <h2 id="lifecycle-title" className="text-sm font-semibold text-slate-900">
        Status
      </h2>
      <p className="mt-1 text-sm text-slate-500">
        {agreement.status === "ACTIVE"
          ? "Pausing skips the bills that fall due while paused. They are not billed later."
          : "Resuming continues on the original schedule. Months skipped while paused are not billed."}
      </p>

      {confirmingCancel ? (
        <div className="mt-4 space-y-3 rounded-md border border-red-200 bg-red-50 p-4">
          <p className="text-sm font-medium text-red-900">
            Cancel this agreement? No further bills will be created. This can't be undone.
          </p>
          <div>
            <label htmlFor="cancel-reason" className="block text-sm text-red-900">
              Reason (optional, kept in the audit log)
            </label>
            <textarea
              id="cancel-reason"
              rows={2}
              maxLength={500}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              className="mt-1 block w-full rounded-md border border-red-200 bg-white px-3 py-2 text-sm focus:border-red-400 focus:outline-none focus:ring-1 focus:ring-red-400"
            />
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={mutation.isPending}
              onClick={() =>
                mutation.mutate({ action: "cancel", version, reason }, { onSettled: () => setConfirmingCancel(false) })
              }
              className="rounded-md bg-red-600 px-3 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-60"
            >
              {mutation.isPending ? "Cancelling…" : "Cancel agreement"}
            </button>
            <button
              type="button"
              disabled={mutation.isPending}
              onClick={() => setConfirmingCancel(false)}
              className={secondary}
            >
              Keep agreement
            </button>
          </div>
        </div>
      ) : (
        <div className="mt-4 flex flex-wrap gap-2">
          {agreement.status === "ACTIVE" && (
            <button
              type="button"
              disabled={mutation.isPending}
              onClick={() => mutation.mutate({ action: "pause", version })}
              className={secondary}
            >
              Pause
            </button>
          )}
          {agreement.status === "PAUSED" && (
            <button
              type="button"
              disabled={mutation.isPending}
              onClick={() => mutation.mutate({ action: "resume", version })}
              className={secondary}
            >
              Resume
            </button>
          )}
          <button
            type="button"
            disabled={mutation.isPending}
            onClick={() => {
              mutation.reset();
              setConfirmingCancel(true);
            }}
            className="rounded-md border border-red-300 bg-white px-3 py-2 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-60"
          >
            Cancel agreement…
          </button>
        </div>
      )}

      {error && (
        <p role="alert" className="mt-3 text-sm text-red-600">
          {error}
        </p>
      )}
    </section>
  );
}
