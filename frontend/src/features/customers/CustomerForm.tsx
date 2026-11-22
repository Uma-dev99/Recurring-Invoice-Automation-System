import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { type FieldError, type UseFormRegisterReturn, useForm } from "react-hook-form";

import { ApiError } from "@/api/client";
import { type CustomerFormValues, customerFormSchema } from "@/schemas/customer";

type DirtyFields = Partial<Record<keyof CustomerFormValues, boolean>>;

interface CustomerFormProps {
  mode: "create" | "edit";
  defaultValues: CustomerFormValues;
  /** The mutation's error, if the last save failed. Server field errors are shown inline. */
  error: unknown;
  isPending: boolean;
  onSubmit: (values: CustomerFormValues, dirtyFields: DirtyFields) => void;
  onCancel: () => void;
}

const FIELD_NAMES = new Set<string>(Object.keys(customerFormSchema.shape));

/**
 * One form for create and edit. Zod checks input while typing; when the server still
 * rejects something (e.g. a duplicate external id, which only the database knows),
 * its field errors from the error envelope are placed on the matching inputs.
 */
export function CustomerForm({ mode, defaultValues, error, isPending, onSubmit, onCancel }: CustomerFormProps) {
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, dirtyFields },
  } = useForm<CustomerFormValues>({ resolver: zodResolver(customerFormSchema), defaultValues });

  useEffect(() => {
    if (!(error instanceof ApiError)) return;
    for (const [field, messages] of Object.entries(error.fieldErrors)) {
      if (FIELD_NAMES.has(field)) {
        setError(field as keyof CustomerFormValues, { type: "server", message: messages[0] });
      }
    }
  }, [error, setError]);

  const formError = describeFormError(error);

  return (
    <form
      onSubmit={handleSubmit((values) => onSubmit(values, dirtyFields as DirtyFields))}
      noValidate
      className="space-y-6"
    >
      {formError && (
        <div role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {formError}
        </div>
      )}

      <fieldset className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <legend className="mb-2 text-sm font-semibold text-slate-900">Customer</legend>
        <TextField
          id="external_customer_id"
          label="External customer id"
          hint={mode === "edit" ? "Fixed after creation." : "The customer's id in your CRM or ERP."}
          registration={register("external_customer_id")}
          error={errors.external_customer_id}
          readOnly={mode === "edit"}
        />
        <div>
          <label htmlFor="customer_type" className="block text-sm font-medium text-slate-700">
            Type
          </label>
          <select id="customer_type" {...register("customer_type")} className={inputClass(false)}>
            <option value="PERSON">Person</option>
            <option value="COMPANY">Company</option>
          </select>
        </div>
        <TextField id="name" label="Name" hint="Full name or company legal name." registration={register("name")} error={errors.name} />
        <TextField id="email" label="Email" type="email" registration={register("email")} error={errors.email} />
        <TextField id="phone" label="Phone (optional)" type="tel" registration={register("phone")} error={errors.phone} />
      </fieldset>

      <fieldset className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <legend className="mb-2 text-sm font-semibold text-slate-900">Billing address</legend>
        <TextField id="address_line1" label="Address" registration={register("address_line1")} error={errors.address_line1} />
        <TextField
          id="address_line2"
          label="Address line 2 (optional)"
          registration={register("address_line2")}
          error={errors.address_line2}
        />
        <TextField id="postal_code" label="Postal code" registration={register("postal_code")} error={errors.postal_code} />
        <TextField id="city" label="City" registration={register("city")} error={errors.city} />
        <TextField
          id="country_code"
          label="Country code"
          hint="Two letters, e.g. NL, DE, BE."
          registration={register("country_code")}
          error={errors.country_code}
          inputClassName="uppercase"
          maxLength={2}
        />
      </fieldset>

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={isPending}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-60"
        >
          {isPending ? "Saving…" : mode === "create" ? "Create customer" : "Save changes"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={isPending}
          className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

function describeFormError(error: unknown): string | null {
  if (!error) return null;
  if (!(error instanceof ApiError)) return "Something went wrong. Please try again.";
  if (error.code !== "validation_error") return error.message;
  // Field errors are shown on the inputs; anything else (non-field errors) goes here.
  const other = Object.entries(error.fieldErrors).filter(([field]) => !FIELD_NAMES.has(field));
  if (other.length === 0) return "Please correct the highlighted fields.";
  return other.map(([field, messages]) => `${field}: ${messages.join(" ")}`).join(" ");
}

function inputClass(invalid: boolean, extra = ""): string {
  return [
    "mt-1 block w-full rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-1 read-only:bg-slate-50 read-only:text-slate-500",
    invalid
      ? "border-red-400 focus:border-red-500 focus:ring-red-500"
      : "border-slate-300 focus:border-slate-500 focus:ring-slate-500",
    extra,
  ].join(" ");
}

interface TextFieldProps {
  id: string;
  label: string;
  registration: UseFormRegisterReturn;
  error?: FieldError;
  hint?: string;
  type?: string;
  readOnly?: boolean;
  maxLength?: number;
  inputClassName?: string;
}

function TextField({ id, label, registration, error, hint, type = "text", readOnly, maxLength, inputClassName }: TextFieldProps) {
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined;
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-slate-700">
        {label}
      </label>
      <input
        id={id}
        type={type}
        readOnly={readOnly}
        maxLength={maxLength}
        aria-invalid={Boolean(error)}
        aria-describedby={describedBy}
        className={inputClass(Boolean(error), inputClassName)}
        {...registration}
      />
      {error ? (
        <p id={`${id}-error`} className="mt-1 text-xs text-red-600">
          {error.message}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className="mt-1 text-xs text-slate-500">
          {hint}
        </p>
      ) : null}
    </div>
  );
}
