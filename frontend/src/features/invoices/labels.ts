import type { AttemptOutcome, InvoiceStatus } from "@/api/invoices";
import type { StatusTone } from "@/components/ui/StatusBadge";

export const INVOICE_STATUSES: InvoiceStatus[] = [
  "PENDING",
  "SUBMITTING",
  "ACCEPTED",
  "REJECTED",
  "RETRY_SCHEDULED",
  "UNKNOWN",
  "NEEDS_ATTENTION",
  "CANCELLED",
];

export const INVOICE_STATUS_LABEL: Record<InvoiceStatus, string> = {
  PENDING: "Pending",
  SUBMITTING: "Submitting",
  ACCEPTED: "Accepted",
  REJECTED: "Rejected",
  RETRY_SCHEDULED: "Retry scheduled",
  UNKNOWN: "Unknown outcome",
  NEEDS_ATTENTION: "Needs attention",
  CANCELLED: "Cancelled",
};

export const INVOICE_STATUS_TONE: Record<InvoiceStatus, StatusTone> = {
  PENDING: "neutral",
  SUBMITTING: "info",
  ACCEPTED: "success",
  REJECTED: "danger",
  RETRY_SCHEDULED: "warning",
  UNKNOWN: "warning",
  NEEDS_ATTENTION: "danger",
  CANCELLED: "neutral",
};

/** One sentence per status: what it means and what happens next. */
export const INVOICE_STATUS_EXPLANATION: Record<InvoiceStatus, string> = {
  PENDING: "Queued; it will be sent to Riverty in the next billing run.",
  SUBMITTING: "Being sent to Riverty right now.",
  ACCEPTED: "Riverty accepted this invoice. Riverty now handles delivery and payment. Accepted does not mean paid.",
  REJECTED: "Riverty refused this invoice. The data must be corrected before it can be sent again.",
  RETRY_SCHEDULED: "A temporary problem; it will be sent again automatically.",
  UNKNOWN:
    "It was sent but no clear answer came back. It is NOT resent blindly (that could invoice twice); the system checks with Riverty first.",
  NEEDS_ATTENTION: "Automatic handling has run out of options. A person needs to look at this.",
  CANCELLED: "An operator decided not to invoice this month. The month is skipped; see the audit log for why.",
};

export const ATTEMPT_OUTCOME_LABEL: Record<AttemptOutcome, string> = {
  IN_PROGRESS: "In progress",
  ACCEPTED: "Accepted",
  REJECTED: "Rejected",
  RETRYABLE: "Temporary failure",
  UNKNOWN: "No clear answer",
};

export const ATTEMPT_OUTCOME_TONE: Record<AttemptOutcome, StatusTone> = {
  IN_PROGRESS: "info",
  ACCEPTED: "success",
  REJECTED: "danger",
  RETRYABLE: "warning",
  UNKNOWN: "warning",
};
