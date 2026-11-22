import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { Controller, useForm } from "react-hook-form";

import type { Agreement } from "@/api/agreements";
import { ApiError } from "@/api/client";
import { CustomerPicker, type PickedCustomer } from "@/features/agreements/CustomerPicker";
import { useCreateAgreement } from "@/features/agreements/hooks";
import {
  type AgreementCreateValues,
  agreementCreateSchema,
  toAmountString,
} from "@/schemas/agreement";
import { todayIsoDay } from "@/utils/format";

interface AgreementCreateFormProps {
  /** Pre-chosen customer (when starting from a customer's page). */
  initialCustomer: PickedCustomer | null;
  onCreated: (agreement: Agreement) => void;
  onCancel: () => void;
}

const FIELDS = new Set(Object.keys(agreementCreateSchema.shape));

const inputClass = (invalid: boolean) =>
  `mt-1 block w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-1 ${
    invalid ? "border-red-400 focus:ring-red-500" : "border-slate-300 focus:border-slate-500 focus:ring-slate-500"
  }`;

export function AgreementCreateForm({ initialCustomer, onCreated, onCancel }: AgreementCreateFormProps) {
  const createAgreement = useCreateAgreement();
  const [customer, setCustomer] = useState<PickedCustomer | null>(initialCustomer);

  const {
    register,
    control,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<AgreementCreateValues>({
    resolver: zodResolver(agreementCreateSchema),
    defaultValues: {
      customer_id: initialCustomer?.id ?? "",
      description: "",
      amount: "",
      anchor_date: "",
      total_cycles: 12,
    },
  });

  // Server-side field errors (e.g. a start date that is already past in the billing
  // time zone) are placed on the matching inputs.
  useEffect(() => {
    const error = createAgreement.error;
    if (!(error instanceof ApiError)) return;
    for (const [field, messages] of Object.entries(error.fieldErrors)) {
      if (FIELDS.has(field)) {
        setError(field as keyof AgreementCreateValues, { type: "server", message: messages[0] });
      }
    }
  }, [createAgreement.error, setError]);

  const onSubmit = (values: AgreementCreateValues) => {
    createAgreement.mutate(
      { ...values, amount: toAmountString(values.amount) },
      { onSuccess: onCreated },
    );
  };

  const error = createAgreement.error;
  const formError =
    error instanceof ApiError && error.code !== "validation_error"
      ? error.message // e.g. "Agreements can only be created for active customers."
      : error && !(error instanceof ApiError)
        ? "Something went wrong. Please try again."
        : null;

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-5">
      {formError && (
        <div role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {formError}
        </div>
      )}

      <div>
        <label htmlFor="customer-picker" className="block text-sm font-medium text-slate-700">
          Customer
        </label>
        <div className="mt-1">
          <Controller
            name="customer_id"
            control={control}
            render={({ field, fieldState }) => (
              <CustomerPicker
                value={customer}
                error={fieldState.error?.message}
                onChange={(picked) => {
                  setCustomer(picked);
                  field.onChange(picked?.id ?? "");
                }}
              />
            )}
          />
        </div>
      </div>

      <div>
        <label htmlFor="description" className="block text-sm font-medium text-slate-700">
          Description
        </label>
        <input
          id="description"
          {...register("description")}
          placeholder="e.g. Gold plan"
          aria-invalid={Boolean(errors.description)}
          className={inputClass(Boolean(errors.description))}
        />
        {errors.description ? (
          <p className="mt-1 text-xs text-red-600">{errors.description.message}</p>
        ) : (
          <p className="mt-1 text-xs text-slate-500">Shown on every invoice.</p>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div>
          <label htmlFor="amount" className="block text-sm font-medium text-slate-700">
            Amount per month
          </label>
          <div className="relative">
            <span className="pointer-events-none absolute inset-y-0 left-3 mt-1 flex items-center text-sm text-slate-500">
              €
            </span>
            <input
              id="amount"
              inputMode="decimal"
              autoComplete="off"
              {...register("amount")}
              placeholder="49.95"
              aria-invalid={Boolean(errors.amount)}
              className={`${inputClass(Boolean(errors.amount))} pl-7 tabular-nums`}
            />
          </div>
          {errors.amount ? (
            <p className="mt-1 text-xs text-red-600">{errors.amount.message}</p>
          ) : (
            <p className="mt-1 text-xs text-slate-500">Including VAT. Euro only.</p>
          )}
        </div>

        <div>
          <label htmlFor="anchor_date" className="block text-sm font-medium text-slate-700">
            First billing date
          </label>
          <input
            id="anchor_date"
            type="date"
            min={todayIsoDay()}
            {...register("anchor_date")}
            aria-invalid={Boolean(errors.anchor_date)}
            className={inputClass(Boolean(errors.anchor_date))}
          />
          {errors.anchor_date && <p className="mt-1 text-xs text-red-600">{errors.anchor_date.message}</p>}
        </div>

        <div>
          <label htmlFor="total_cycles" className="block text-sm font-medium text-slate-700">
            Number of months
          </label>
          <input
            id="total_cycles"
            type="number"
            min={1}
            max={120}
            {...register("total_cycles", { valueAsNumber: true })}
            aria-invalid={Boolean(errors.total_cycles)}
            className={`${inputClass(Boolean(errors.total_cycles))} tabular-nums`}
          />
          {errors.total_cycles && <p className="mt-1 text-xs text-red-600">{errors.total_cycles.message}</p>}
        </div>
      </div>

      <p className="text-xs text-slate-500">
        Amount, first billing date and number of months can't be changed later. To correct them, cancel the
        agreement and create a new one.
      </p>

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={createAgreement.isPending}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-60"
        >
          {createAgreement.isPending ? "Creating…" : "Create agreement"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={createAgreement.isPending}
          className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
