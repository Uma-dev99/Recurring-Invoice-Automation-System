import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getAttentionSummary,
  listFailedEvents,
  listMissedPeriods,
  requeueFailedEvent,
  runMissedPeriodAction,
} from "@/api/attention";
import { ApiError } from "@/api/client";
import {
  getInvoice,
  type InvoiceActionInput,
  type InvoiceListParams,
  listInvoices,
  runInvoiceAction,
} from "@/api/invoices";
import { queryKeys } from "@/api/queryKeys";

/**
 * Invoices change in the BACKGROUND (the jobs submit, retry, reconcile), not because of
 * anything done on this screen. So unlike customers and agreements, these queries poll:
 * every 30 s while a page that uses them is open.
 */
const POLL_MS = 30_000;

export function useInvoices(params: InvoiceListParams, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: queryKeys.invoices.list(params),
    queryFn: ({ signal }) => listInvoices(params, signal),
    placeholderData: keepPreviousData,
    refetchInterval: POLL_MS,
    enabled: options.enabled,
  });
}

export function useInvoice(id: string) {
  return useQuery({
    queryKey: queryKeys.invoices.detail(id),
    queryFn: ({ signal }) => getInvoice(id, signal),
    refetchInterval: POLL_MS,
  });
}

export function useAttentionSummary() {
  return useQuery({
    queryKey: queryKeys.attention.summary(),
    queryFn: ({ signal }) => getAttentionSummary(signal),
    refetchInterval: POLL_MS,
  });
}

export function useMissedPeriods(page: number) {
  return useQuery({
    queryKey: queryKeys.attention.missedPeriods(page),
    queryFn: ({ signal }) => listMissedPeriods(page, signal),
    placeholderData: keepPreviousData,
    refetchInterval: POLL_MS,
  });
}

export function useFailedEvents(page: number) {
  return useQuery({
    queryKey: queryKeys.attention.failedEvents(page),
    queryFn: ({ signal }) => listFailedEvents(page, signal),
    placeholderData: keepPreviousData,
    refetchInterval: POLL_MS,
  });
}

export function isInvoiceChanged(error: unknown): boolean {
  return error instanceof ApiError && error.code === "invoice_changed";
}

/**
 * After any operator action: an invoice, a month or an agreement changed somewhere, and
 * the attention counts with them. Refresh all of it rather than guess what moved.
 */
function useRefreshAfterAction() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.invoices.all }),
      queryClient.invalidateQueries({ queryKey: queryKeys.attention.all }),
      queryClient.invalidateQueries({ queryKey: queryKeys.agreements.all }),
    ]);
}

export function useInvoiceAction(id: string) {
  const queryClient = useQueryClient();
  const refresh = useRefreshAfterAction();
  return useMutation({
    mutationFn: (input: InvoiceActionInput) => runInvoiceAction(id, input),
    onSuccess: (invoice) => {
      queryClient.setQueryData(queryKeys.invoices.detail(id), invoice);
      return refresh();
    },
    // 409: someone or something changed it meanwhile; show the current state.
    onError: (error) => (isInvoiceChanged(error) ? refresh() : undefined),
  });
}

export function useMissedPeriodAction() {
  const refresh = useRefreshAfterAction();
  return useMutation({
    mutationFn: ({ id, action, reason }: { id: string; action: "invoice-now" | "skip"; reason: string }) =>
      runMissedPeriodAction(id, action, reason),
    onSettled: refresh,
  });
}

export function useRequeueFailedEvent() {
  const refresh = useRefreshAfterAction();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => requeueFailedEvent(id, reason),
    onSettled: refresh,
  });
}
