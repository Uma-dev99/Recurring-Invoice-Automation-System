/** Server state for agreements (see features/customers/hooks.ts for the pattern). */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type Agreement,
  type AgreementAction,
  type AgreementListParams,
  createAgreement,
  getAgreement,
  listAgreements,
  runAgreementAction,
  updateAgreement,
  VERSION_CONFLICT_CODE,
} from "@/api/agreements";
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

/**
 * After a write: cache the fresh agreement and refresh every agreement list (the main
 * list and each customer's panel). After a version conflict: refetch the agreement, so
 * the page shows what the other person saved and the next attempt uses the new version.
 */
function useAgreementCache() {
  const queryClient = useQueryClient();
  return {
    store: (agreement: Agreement) => {
      queryClient.setQueryData(queryKeys.agreements.detail(agreement.id), agreement);
      return queryClient.invalidateQueries({ queryKey: queryKeys.agreements.lists() });
    },
    refreshOnConflict: (id: string, error: unknown) => {
      if (isVersionConflict(error)) {
        return queryClient.invalidateQueries({ queryKey: queryKeys.agreements.detail(id) });
      }
    },
  };
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
