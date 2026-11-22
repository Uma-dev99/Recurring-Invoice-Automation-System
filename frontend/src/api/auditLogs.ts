/** GET /api/v1/audit-logs/: the append-only history of every change. Read-only. */
import { apiRequest, type Paginated } from "@/api/client";

export interface AuditEntry {
  id: string;
  created_at: string;
  /** "<record>.<what happened>", e.g. "agreement.paused", "invoice.operator_retried". */
  action: string;
  /** Model label, e.g. "customers.customer". */
  entity_type: string;
  entity_id: string;
  /** null = done by the system (background jobs), not a person. */
  actor: { id: string; email: string; full_name: string } | null;
  /** What changed. Updates use {field: {old, new}}; other actions store plain values. */
  changes: Record<string, unknown>;
}

export interface AuditLogParams {
  page?: number;
  page_size?: number;
  action?: string;
  entity_type?: string;
  entity_id?: string;
  /** A user id, or "system". */
  actor?: string;
  date_from?: string;
  date_to?: string;
}

export interface AuditFilterOptions {
  actions: string[];
  entity_types: string[];
}

export function listAuditLogs(params: AuditLogParams, signal?: AbortSignal) {
  return apiRequest<Paginated<AuditEntry>>("/audit-logs/", { query: { ...params }, signal });
}

export function getAuditFilterOptions(signal?: AbortSignal) {
  return apiRequest<AuditFilterOptions>("/audit-logs/filters/", { signal });
}
