/**
 * Endpoint functions for /api/v1/agreements/. Types mirror the backend serializers.
 *
 * Every write sends `version`: the version of the agreement the user was looking at.
 * If someone else changed it meanwhile, the API answers 409 with code
 * "agreement_version_conflict" and nothing is changed.
 */
import { apiRequest, type Paginated } from "@/api/client";
import type { CustomerStatus } from "@/api/customers";

export type AgreementStatus = "ACTIVE" | "PAUSED" | "CANCELLED" | "COMPLETED";

export interface Agreement {
  id: string;
  customer: { id: string; name: string; external_customer_id: string; status: CustomerStatus };
  description: string;
  /** Money as a string ("49.95"): exact, unlike a JavaScript number. VAT included. */
  amount: string;
  currency: "EUR";
  /** First billing day, "YYYY-MM-DD". */
  anchor_date: string;
  total_cycles: number;
  status: AgreementStatus;
  cancelled_at: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface AgreementCreateInput {
  customer_id: string;
  description: string;
  amount: string;
  anchor_date: string;
  total_cycles: number;
}

export type AgreementOrdering =
  | "created_at"
  | "-created_at"
  | "anchor_date"
  | "-anchor_date"
  | "amount"
  | "-amount";

export interface AgreementListParams {
  page?: number;
  page_size?: number;
  customer?: string;
  status?: AgreementStatus;
  search?: string;
  ordering?: AgreementOrdering;
}

export type AgreementAction =
  | { action: "pause"; version: number }
  | { action: "resume"; version: number }
  | { action: "cancel"; version: number; reason: string };

export const VERSION_CONFLICT_CODE = "agreement_version_conflict";

export function listAgreements(params: AgreementListParams, signal?: AbortSignal) {
  return apiRequest<Paginated<Agreement>>("/agreements/", { query: { ...params }, signal });
}

export function getAgreement(id: string, signal?: AbortSignal) {
  return apiRequest<Agreement>(`/agreements/${id}/`, { signal });
}

export function createAgreement(input: AgreementCreateInput) {
  return apiRequest<Agreement>("/agreements/", { method: "POST", body: input });
}

export function updateAgreement(id: string, input: { version: number; description: string }) {
  return apiRequest<Agreement>(`/agreements/${id}/`, { method: "PATCH", body: input });
}

export function runAgreementAction(id: string, { action, ...body }: AgreementAction) {
  return apiRequest<Agreement>(`/agreements/${id}/${action}/`, { method: "POST", body });
}
