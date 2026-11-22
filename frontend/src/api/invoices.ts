/** Endpoint functions for /api/v1/invoices/. Types mirror the serializers. */
import { apiRequest, type Paginated } from "@/api/client";

export type InvoiceStatus =
  | "PENDING"
  | "SUBMITTING"
  | "ACCEPTED"
  | "REJECTED"
  | "RETRY_SCHEDULED"
  | "UNKNOWN"
  | "NEEDS_ATTENTION"
  | "CANCELLED";

/** Operator actions the SERVER says are possible right now (the screen shows only these). */
export type InvoiceAction = "retry" | "mark_received" | "cancel";

export interface Invoice {
  id: string;
  /** Our reference, also known to Riverty; stable across retries. */
  merchant_reference: string;
  status: InvoiceStatus;
  amount: string;
  currency: "EUR";
  /** Riverty's invoice number once accepted, else "". */
  external_invoice_id: string;
  attempt_count: number;
  next_attempt_at: string | null;
  accepted_at: string | null;
  last_error_category: string;
  last_error_message: string;
  period: { id: string; cycle_number: number; period_start: string; period_end: string };
  agreement: { id: string; description: string };
  customer: { id: string; name: string };
  created_at: string;
  updated_at: string;
}

export type AttemptOutcome = "IN_PROGRESS" | "ACCEPTED" | "REJECTED" | "RETRYABLE" | "UNKNOWN";

export interface ProcessingAttempt {
  attempt_number: number;
  outcome: AttemptOutcome;
  error_category: string;
  error_message: string;
  request_summary: Record<string, unknown>;
  response_summary: Record<string, unknown>;
  started_at: string;
  finished_at: string | null;
}

export interface InvoiceDetail extends Invoice {
  attempts: ProcessingAttempt[];
  available_actions: InvoiceAction[];
  /** The latest attempt got no clear answer: Riverty may already have this invoice. */
  may_exist_at_riverty: boolean;
}

export type InvoiceOrdering = "created_at" | "-created_at" | "period_start" | "-period_start";

export interface InvoiceListParams {
  page?: number;
  page_size?: number;
  status?: InvoiceStatus;
  agreement?: string;
  search?: string;
  /** Only submissions that should have moved on by now (background jobs may be down). */
  stuck?: boolean;
  ordering?: InvoiceOrdering;
}

export function listInvoices(params: InvoiceListParams, signal?: AbortSignal) {
  return apiRequest<Paginated<Invoice>>("/invoices/", { query: { ...params }, signal });
}

export function getInvoice(id: string, signal?: AbortSignal) {
  return apiRequest<InvoiceDetail>(`/invoices/${id}/`, { signal });
}

/**
 * Operator actions. Each sends the status the operator was looking at; if the invoice
 * changed meanwhile the API answers 409 "invoice_changed" and does nothing.
 */
interface ActionBase {
  expected_status: InvoiceStatus;
  reason: string;
}

export type InvoiceActionInput =
  | ({ action: "retry" } & ActionBase & { confirmed_not_at_riverty: boolean })
  | ({ action: "cancel" } & ActionBase & { confirmed_not_at_riverty: boolean })
  | ({ action: "mark_received" } & ActionBase & { external_invoice_id: string });

const ACTION_PATH: Record<InvoiceAction, string> = {
  retry: "retry",
  cancel: "cancel",
  mark_received: "mark-received",
};

export function runInvoiceAction(id: string, { action, ...body }: InvoiceActionInput) {
  return apiRequest<InvoiceDetail>(`/invoices/${id}/${ACTION_PATH[action]}/`, { method: "POST", body });
}
