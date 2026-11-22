/** Endpoint functions for /api/v1/attention/: what the system needs a person for. */
import { apiRequest, type Paginated } from "@/api/client";

export interface AttentionSummary {
  needs_attention: number;
  rejected: number;
  unknown: number;
  /** Should have been sent by now but wasn't: background jobs may be down. */
  stuck: number;
  /** Months of active agreements that ended without an invoice. */
  missed_periods: number;
  /** Background work that gave up after repeated errors. */
  failed_events: number;
  /** Informational: being retried automatically, not counted in `total`. */
  retry_scheduled: number;
  total: number;
}

export interface MissedPeriod {
  id: string;
  cycle_number: number;
  period_start: string;
  period_end: string;
  amount: string;
  currency: "EUR";
  agreement: { id: string; description: string };
  customer: { id: string; name: string };
}

export interface FailedEvent {
  id: string;
  event_type: string;
  payload: Record<string, unknown>;
  attempts: number;
  last_error: string;
  created_at: string;
  available_at: string;
}

export function getAttentionSummary(signal?: AbortSignal) {
  return apiRequest<AttentionSummary>("/attention/summary/", { signal });
}

export function listMissedPeriods(page: number, signal?: AbortSignal) {
  return apiRequest<Paginated<MissedPeriod>>("/attention/missed-periods/", { query: { page }, signal });
}

export function runMissedPeriodAction(id: string, action: "invoice-now" | "skip", reason: string) {
  return apiRequest<MissedPeriod>(`/attention/missed-periods/${id}/${action}/`, {
    method: "POST",
    body: { reason },
  });
}

export function listFailedEvents(page: number, signal?: AbortSignal) {
  return apiRequest<Paginated<FailedEvent>>("/attention/failed-events/", { query: { page }, signal });
}

export function requeueFailedEvent(id: string, reason: string) {
  return apiRequest<FailedEvent>(`/attention/failed-events/${id}/requeue/`, {
    method: "POST",
    body: { reason },
  });
}
