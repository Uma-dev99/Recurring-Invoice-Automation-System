import { useState } from "react";

import { ApiError } from "@/api/client";
import type { InvoiceAction, InvoiceDetail } from "@/api/invoices";
import { isInvoiceChanged, useInvoiceAction } from "@/features/invoices/hooks";

const MIN_REASON = 5;

const ACTION_TEXT: Record<InvoiceAction, { button: string; title: string; help: string }> = {
  retry: {
    button: "Retry now",
    title: "Send this invoice to Riverty again",
    help: "It is sent within seconds. If it fails temporarily, automatic retries start again.",
  },
  mark_received: {
    button: "Mark as received…",
    title: "Riverty has this invoice",
    help: "Use this when you found the invoice at Riverty (portal or support). It becomes Accepted.",
  },
  cancel: {
    button: "Don't invoice this month…",
    title: "Give up on invoicing this month",
    help: "The invoice is cancelled and the month is skipped. This can't be undone.",
  },
};

/**
 * What a person can do with an invoice the system couldn't handle alone.
 *
 * The SERVER decides which actions exist (available_actions) and enforces every rule;
 * this panel only explains them. In particular, when Riverty may already have the
 * invoice, retry and cancel stay disabled until the operator confirms they checked.
 */
export function OperatorActions({ invoice }: { invoice: InvoiceDetail }) {
  const [open, setOpen] = useState<InvoiceAction | null>(null);
  const mutation = useInvoiceAction(invoice.id);

  if (invoice.available_actions.length === 0) return null;

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-6" aria-labelledby="actions-title">
      <h2 id="actions-title" className="text-sm font-semibold text-slate-900">
        What to do
      </h2>

      {invoice.may_exist_at_riverty && (
        <div className="mt-3 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          <span className="font-medium">Riverty may already have this invoice.</span> The last attempt got no clear
          answer. Check with Riverty (portal or support) before retrying or cancelling: sending it again could invoice
          the customer twice.
        </div>
      )}

      {isInvoiceChanged(mutation.error) && (
        <div role="alert" className="mt-3 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          This invoice changed while you were looking at it, so nothing was done. The page now shows its current
          state.
        </div>
      )}

      {open ? (
        <ActionForm
          key={open}
          action={open}
          invoice={invoice}
          mutation={mutation}
          onClose={() => setOpen(null)}
        />
      ) : (
        <div className="mt-4 flex flex-wrap gap-2">
          {invoice.available_actions.map((action) => (
            <button
              key={action}
              type="button"
              onClick={() => {
                mutation.reset();
                setOpen(action);
              }}
              className={
                action === "cancel"
                  ? "rounded-md border border-red-300 bg-white px-3 py-2 text-sm font-medium text-red-700 hover:bg-red-50"
                  : "rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              }
            >
              {ACTION_TEXT[action].button}
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

function ActionForm({
  action,
  invoice,
  mutation,
  onClose,
}: {
  action: InvoiceAction;
  invoice: InvoiceDetail;
  mutation: ReturnType<typeof useInvoiceAction>;
  onClose: () => void;
}) {
  const [reason, setReason] = useState("");
  const [rivertyNumber, setRivertyNumber] = useState("");
  const [checked, setChecked] = useState(false);

  const needsCheck = invoice.may_exist_at_riverty && action !== "mark_received";
  const ready =
    reason.trim().length >= MIN_REASON &&
    (!needsCheck || checked) &&
    (action !== "mark_received" || rivertyNumber.trim().length > 0);

  const submit = () => {
    const base = { expected_status: invoice.status, reason: reason.trim() };
    const input =
      action === "mark_received"
        ? { action, ...base, external_invoice_id: rivertyNumber.trim() }
        : { action, ...base, confirmed_not_at_riverty: checked };
    mutation.mutate(input, { onSuccess: onClose, onError: (error) => isInvoiceChanged(error) && onClose() });
  };

  const error = mutation.error instanceof ApiError && !isInvoiceChanged(mutation.error) ? mutation.error : null;
  const text = ACTION_TEXT[action];

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (ready) submit();
      }}
      className="mt-4 space-y-3 rounded-md border border-slate-200 bg-slate-50 p-4"
    >
      <div>
        <p className="text-sm font-medium text-slate-900">{text.title}</p>
        <p className="text-xs text-slate-600">{text.help}</p>
      </div>

      {action === "mark_received" && (
        <div>
          <label htmlFor="riverty-number" className="block text-sm text-slate-700">
            Riverty's invoice number
          </label>
          <input
            id="riverty-number"
            value={rivertyNumber}
            onChange={(event) => setRivertyNumber(event.target.value)}
            className="mt-1 block w-full max-w-xs rounded-md border border-slate-300 bg-white px-3 py-2 font-mono text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
          />
          {error?.fieldErrors.external_invoice_id && (
            <p className="mt-1 text-xs text-red-600">{error.fieldErrors.external_invoice_id[0]}</p>
          )}
        </div>
      )}

      <div>
        <label htmlFor="action-reason" className="block text-sm text-slate-700">
          Reason (kept in the audit log)
        </label>
        <textarea
          id="action-reason"
          rows={2}
          maxLength={500}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          placeholder={action === "retry" ? "e.g. Customer address corrected" : ""}
          className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
        />
        {error?.fieldErrors.reason && <p className="mt-1 text-xs text-red-600">{error.fieldErrors.reason[0]}</p>}
      </div>

      {needsCheck && (
        <label className="flex items-start gap-2 text-sm text-slate-800">
          <input
            type="checkbox"
            checked={checked}
            onChange={(event) => setChecked(event.target.checked)}
            className="mt-0.5"
          />
          <span>
            I checked with Riverty: invoice <span className="font-mono">{invoice.merchant_reference}</span> does
            <span className="font-semibold"> not</span> exist there.
          </span>
        </label>
      )}

      {error && !error.fieldErrors.reason && !error.fieldErrors.external_invoice_id && (
        <p role="alert" className="text-sm text-red-700">
          {error.message}
        </p>
      )}

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={!ready || mutation.isPending}
          className={`rounded-md px-3 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50 ${
            action === "cancel" ? "bg-red-600 hover:bg-red-700" : "bg-slate-900 hover:bg-slate-800"
          }`}
        >
          {mutation.isPending ? "Working…" : text.button.replace("…", "")}
        </button>
        <button
          type="button"
          onClick={onClose}
          disabled={mutation.isPending}
          className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          Back
        </button>
      </div>
    </form>
  );
}
