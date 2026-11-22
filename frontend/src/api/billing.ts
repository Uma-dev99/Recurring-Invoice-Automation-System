/** Endpoint functions for billing periods (an agreement's monthly schedule). */
import { apiRequest } from "@/api/client";

export type PeriodStatus = "SCHEDULED" | "INVOICING" | "INVOICED" | "SKIPPED" | "CANCELLED";

export interface BillingPeriod {
  id: string;
  /** 1 = the first month. */
  cycle_number: number;
  /** Billing date: the invoice may go out from this day ("YYYY-MM-DD"). */
  period_start: string;
  /** Last day covered, and the deadline: Riverty refuses invoices after it. */
  period_end: string;
  /** Snapshot taken when the period was created (or repriced). VAT included. */
  amount: string;
  currency: "EUR";
  status: PeriodStatus;
}

/** The whole schedule, month 1 first. Not paginated (at most 120 months). */
export function listAgreementPeriods(agreementId: string, signal?: AbortSignal) {
  return apiRequest<BillingPeriod[]>(`/agreements/${agreementId}/periods/`, { signal });
}
