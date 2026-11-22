/** Server state for agreements (see features/customers/hooks.ts for the pattern). */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type Agreement,
  type AgreementAction,
  type AgreementListParams,
  type ChangeAmountInput,
  changeAgreementAmount,
  createAgreement,
  getAgreement,
  listAgreements,
  runAgreementAction,
  updateAgreement,
  VERSION_CONFLICT_CODE,
} from "@/api/agreements";
import { listAgreementPeriods } from "@/api/billing";
import { ApiError } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";

export function useAgreements(params: AgreementListParams, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: queryKeys.agreements.list(params),
    queryFn: ({ signal }) => listAgreements(params, signal),
    placeholderData: keepPreviousData,
    enabled: options.enabled,
  });
}

export function useAgreement(id: string) {
  return useQuery({
    queryKey: queryKeys.agreements.detail(id),
    queryFn: ({ signal }) => getAgreement(id, signal),
  });
}

export function isVersionConflict(error: unknown): boolean {
  return error instanceof ApiError && error.code === VERSION_CONFLICT_CODE;
}

export function useAgreementPeriods(agreementId: string) {
  return useQuery({
    queryKey: queryKeys.agreements.periods(agreementId),
    queryFn: ({ signal }) => listAgreementPeriods(agreementId, signal),
  });
}

/**
 * After a write: cache the fresh agreement, refresh every agreement list (the main list
 * and each customer's panel) and this agreement's schedule, because every agreement
 * action can change its periods (pause/resume/cancel skip or cancel months, a price
 * change reprices them).
 * After a version conflict: refetch the agreement AND its schedule (the schedule key
 * lives under the agreement's key, so one prefix invalidation covers both), so the page
 * shows what the other person saved and the next attempt uses the new version.
 */
function useAgreementCache() {
  const queryClient = useQueryClient();
  return {
    store: (agreement: Agreement) => {
      queryClient.setQueryData(queryKeys.agreements.detail(agreement.id), agreement);
      return Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.agreements.lists() }),
        queryClient.invalidateQueries({ queryKey: queryKeys.agreements.periods(agreement.id) }),
      ]);
    },
    refreshOnConflict: (id: string, error: unknown) => {
      if (isVersionConflict(error)) {
        return queryClient.invalidateQueries({ queryKey: queryKeys.agreements.detail(id) });
      }
    },
  };
}

export function useChangeAgreementAmount(id: string) {
  const { store, refreshOnConflict } = useAgreementCache();
  return useMutation({
    mutationFn: (input: ChangeAmountInput) => changeAgreementAmount(id, input),
    onSuccess: store,
    onError: (error) => refreshOnConflict(id, error),
  });
}

export function useCreateAgreement() {
  const { store } = useAgreementCache();
  return useMutation({ mutationFn: createAgreement, onSuccess: store });
}

export function useUpdateAgreement(id: string) {
  const { store, refreshOnConflict } = useAgreementCache();
  return useMutation({
    mutationFn: (input: { version: number; description: string }) => updateAgreement(id, input),
    onSuccess: store,
    onError: (error) => refreshOnConflict(id, error),
  });
}

export function useAgreementAction(id: string) {
  const { store, refreshOnConflict } = useAgreementCache();
  return useMutation({
    mutationFn: (input: AgreementAction) => runAgreementAction(id, input),
    onSuccess: store,
    onError: (error) => refreshOnConflict(id, error),
  });
}
