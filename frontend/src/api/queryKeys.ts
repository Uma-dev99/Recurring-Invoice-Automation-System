/**
 * Central registry of TanStack Query cache keys.
 *
 * Keys are hierarchical arrays. Invalidating ["customers"] later refreshes every
 * customer list and detail query at once, so keys must be built consistently.
 */
import type { AgreementListParams } from "@/api/agreements";
import type { CustomerListParams } from "@/api/customers";

const CUSTOMERS = ["customers"] as const;
const AGREEMENTS = ["agreements"] as const;

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
  },
};
