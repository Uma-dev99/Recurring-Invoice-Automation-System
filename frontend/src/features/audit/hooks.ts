import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { type AuditLogParams, getAuditFilterOptions, listAuditLogs } from "@/api/auditLogs";
import { getDashboard } from "@/api/dashboard";
import { queryKeys } from "@/api/queryKeys";

/** Both change in the background (jobs act all day), so they refresh every 30 s. */
const POLL_MS = 30_000;

export function useAuditLogs(params: AuditLogParams, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: queryKeys.auditLogs.list(params),
    queryFn: ({ signal }) => listAuditLogs(params, signal),
    placeholderData: keepPreviousData,
    refetchInterval: POLL_MS,
    enabled: options.enabled,
  });
}

export function useAuditFilterOptions() {
  return useQuery({
    queryKey: queryKeys.auditLogs.filters(),
    queryFn: ({ signal }) => getAuditFilterOptions(signal),
    staleTime: 5 * 60_000,
  });
}

export function useDashboard() {
  return useQuery({
    queryKey: queryKeys.dashboard,
    queryFn: ({ signal }) => getDashboard(signal),
    refetchInterval: POLL_MS,
  });
}
