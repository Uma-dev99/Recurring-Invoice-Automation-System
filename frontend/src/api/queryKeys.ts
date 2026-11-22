/**
 * Central registry of TanStack Query cache keys.
 *
 * Keys are hierarchical arrays. Invalidating ["customers"] later refreshes every
 * customer list and detail query at once, so keys must be built consistently.
 */
import type { AgreementListParams } from "@/api/agreements";
import type { AuditLogParams } from "@/api/auditLogs";
import type { CustomerListParams } from "@/api/customers";
import type { InvoiceListParams } from "@/api/invoices";

const CUSTOMERS = ["customers"] as const;
const AGREEMENTS = ["agreements"] as const;
const INVOICES = ["invoices"] as const;
const ATTENTION = ["attention"] as const;

export const queryKeys = {
  auth: {
    me: ["auth", "me"] as const,
  },
  health: ["health"] as const,
  customers: {
    all: CUSTOMERS,
    lists: () => [...CUSTOMERS, "list"] as const,
    // Params are part of the key: page 2 and page 3 are cached separately.
    list: (params: CustomerListParams) => [...CUSTOMERS, "list", params] as const,
    detail: (id: string) => [...CUSTOMERS, "detail", id] as const,
  },
  agreements: {
    all: AGREEMENTS,
    lists: () => [...AGREEMENTS, "list"] as const,
    list: (params: AgreementListParams) => [...AGREEMENTS, "list", params] as const,
    detail: (id: string) => [...AGREEMENTS, "detail", id] as const,
    // Lives under the agreement's key, so anything that refreshes "this agreement"
    // can refresh its schedule too.
    periods: (id: string) => [...AGREEMENTS, "detail", id, "periods"] as const,
  },
  invoices: {
    all: INVOICES,
    list: (params: InvoiceListParams) => [...INVOICES, "list", params] as const,
    detail: (id: string) => [...INVOICES, "detail", id] as const,
  },
  dashboard: ["dashboard"] as const,
  auditLogs: {
    all: ["audit-logs"] as const,
    list: (params: AuditLogParams) => ["audit-logs", "list", params] as const,
    filters: () => ["audit-logs", "filters"] as const,
  },
  attention: {
    all: ATTENTION,
    summary: () => [...ATTENTION, "summary"] as const,
    missedPeriods: (page: number) => [...ATTENTION, "missed-periods", page] as const,
    failedEvents: (page: number) => [...ATTENTION, "failed-events", page] as const,
  },
};
