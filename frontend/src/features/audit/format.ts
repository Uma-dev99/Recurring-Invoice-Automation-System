/** Turning raw audit values ("invoice.operator_retried", model labels) into words. */

const RECORD_NAME: Record<string, string> = {
  "customers.customer": "Customer",
  "agreements.billingagreement": "Agreement",
  "billing.billingperiod": "Billing month",
  "invoicing.invoicesubmission": "Invoice",
  "operations.outboxevent": "Background job",
};

/** Where a record lives in the app, or null if it has no page of its own. */
export function recordLink(entityType: string, entityId: string): string | null {
  switch (entityType) {
    case "customers.customer":
      return `/customers/${entityId}`;
    case "agreements.billingagreement":
      return `/agreements/${entityId}`;
    case "invoicing.invoicesubmission":
      return `/invoices/${entityId}`;
    case "operations.outboxevent":
      return "/jobs?tab=failed";
    default:
      return null;
  }
}

export function recordName(entityType: string): string {
  return RECORD_NAME[entityType] ?? entityType;
}

/** "invoice.operator_retried" -> "Operator retried"; the record type is shown separately. */
export function actionLabel(action: string): string {
  const verb = action.includes(".") ? action.slice(action.indexOf(".") + 1) : action;
  const words = verb.replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** One change value as short text: {old, new} -> "old → new"; objects -> JSON. */
export function changeText(value: unknown): string {
  if (value && typeof value === "object" && "old" in value && "new" in value) {
    const { old, new: next } = value as { old: unknown; new: unknown };
    return `${plain(old)} → ${plain(next)}`;
  }
  return plain(value);
}

function plain(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
