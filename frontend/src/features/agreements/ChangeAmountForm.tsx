import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm, useWatch } from "react-hook-form";

import type { Agreement } from "@/api/agreements";
import type { BillingPeriod } from "@/api/billing";
import { ApiError } from "@/api/client";
import { isVersionConflict, useChangeAgreementAmount } from "@/features/agreements/hooks";
import { LOCKED_STATUSES } from "@/features/billing/labels";
import { type ChangeAmountValues, changeAmountSchema, toAmountString } from "@/schemas/agreement";
import { formatMoney } from "@/utils/format";

interface ChangeAmountFormProps {
  agreement: Agreement;
  periods: BillingPeriod[];
  mutation: ReturnType<typeof useChangeAgreementAmount>;
  /** Tells the schedule table which month to highlight from (undefined = none). */
  onPreview: (fromCycle: number | undefined) => void;
  onDone: () => void;
}

/**
 * Months a new price may start from: any SCHEDULED month after the last month that is
 * being or has been invoiced (an invoice must never disagree with its month). This only
 * shapes the choices; the server checks the same rule and its answer wins.
 */
export function eligibleStartMonths(periods: BillingPeriod[]): number[] {
  const lastLocked = Math.max(
    0,
    ...periods.filter((p) => LOCKED_STATUSES.includes(p.status)).map((p) => p.cycle_number),
  );
  return periods.filter((p) => p.status === "SCHEDULED" && p.cycle_number > lastLocked).map((p) => p.cycle_number);
}

export function ChangeAmountForm({ agreement, periods, mutation, onPreview, onDone }: ChangeAmountFormProps) {
  const months = eligibleStartMonths(periods);

  const {
    register,
    handleSubmit,
    control,
    setError,
    formState: { errors },
  } = useForm<ChangeAmountValues>({
    resolver: zodResolver(changeAmountSchema),
    defaultValues: { from_cycle: months[0], amount: "" },
  });

  const fromCycle = useWatch({ control, name: "from_cycle" });
  const amountInput = useWatch({ control, name: "amount" });

  // Highlight the affected rows while the form is open; clear it when it closes.
  useEffect(() => {
    onPreview(fromCycle);
    return () => onPreview(undefined);
  }, [fromCycle, onPreview]);

  // Server field errors (e.g. from_cycle beyond the schedule) go on the inputs.
  useEffect(() => {
    const error = mutation.error;
    if (!(error instanceof ApiError)) return;
    for (const field of ["from_cycle", "amount"] as const) {
      const message = error.fieldErrors[field]?.[0];
      if (message) setError(field, { type: "server", message });
    }
  }, [mutation.error, setError]);

  const affected = periods.filter((p) => p.status === "SCHEDULED" && p.cycle_number >= fromCycle);
  const currentAmounts = [...new Set(affected.map((p) => p.amount))];
  const validAmount = changeAmountSchema.shape.amount.safeParse(amountInput).success;

  const onSubmit = (values: ChangeAmountValues) => {
    mutation.mutate(
      { version: agreement.version, from_cycle: values.from_cycle, amount: toAmountString(values.amount) },
      {
        onSuccess: onDone,
        // On a conflict, close: the person must first see the schedule someone else changed.
        onError: (error) => isVersionConflict(error) && onDone(),
      },
    );
  };

  const formError =
    mutation.error instanceof ApiError && mutation.error.code !== "validation_error" && !isVersionConflict(mutation.error)
      ? mutation.error.message // e.g. "Month 3 is already invoiced. Choose a later month."
      : mutation.error && !(mutation.error instanceof ApiError)
        ? "Something went wrong. Please try again."
        : null;

  if (months.length === 0) {
    return (
      <div className="rounded-md border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
        No months are left whose price can still change.{" "}
        <button type="button" onClick={onDone} className="font-medium underline underline-offset-2">
          Close
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4 rounded-md border border-amber-200 bg-amber-50/50 p-4">
      <h3 className="text-sm font-semibold text-slate-900">Change the monthly price</h3>
      {formError && (
        <div role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {formError}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="from_cycle" className="block text-sm font-medium text-slate-700">
            From month
          </label>
          <select
            id="from_cycle"
            {...register("from_cycle", { valueAsNumber: true })}
            className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
          >
            {months.map((month) => (
              <option key={month} value={month}>
                Month {month}
              </option>
            ))}
          </select>
          {errors.from_cycle && <p className="mt-1 text-xs text-red-600">{errors.from_cycle.message}</p>}
        </div>

        <div>
          <label htmlFor="new_amount" className="block text-sm font-medium text-slate-700">
            New amount per month
          </label>
          <div className="relative">
            <span className="pointer-events-none absolute inset-y-0 left-3 mt-1 flex items-center text-sm text-slate-500">
              €
            </span>
            <input
              id="new_amount"
              inputMode="decimal"
              autoComplete="off"
              {...register("amount")}
              placeholder={agreement.amount}
              aria-invalid={Boolean(errors.amount)}
              className="mt-1 block w-full rounded-md border border-slate-300 bg-white py-2 pr-3 pl-7 text-sm tabular-nums focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
            />
          </div>
          {errors.amount ? (
            <p className="mt-1 text-xs text-red-600">{errors.amount.message}</p>
          ) : (
            <p className="mt-1 text-xs text-slate-500">Including VAT.</p>
          )}
        </div>
      </div>

      {affected.length > 0 && (
        <p className="text-sm text-slate-700" aria-live="polite">
          {affected.length === 1 ? "1 month" : `${affected.length} months`} (highlighted below) will change from{" "}
          {currentAmounts.map((a) => formatMoney(a)).join(" / ")}
          {validAmount ? (
            <>
              {" "}
              to <span className="font-semibold">{formatMoney(toAmountString(amountInput))}</span>
            </>
          ) : null}
          . Earlier months keep their price.
        </p>
      )}

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={mutation.isPending}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-60"
        >
          {mutation.isPending ? "Saving…" : "Change price"}
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
