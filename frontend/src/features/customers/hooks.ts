/**
 * Server state for customers. Pages use these hooks and never call fetch or copy API
 * data into useState: TanStack Query owns caching, loading/error state and refetching.
 */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type Customer,
  type CustomerListParams,
  type CustomerUpdateInput,
  createCustomer,
  deactivateCustomer,
  getCustomer,
  listCustomers,
  reactivateCustomer,
  updateCustomer,
} from "@/api/customers";
import { queryKeys } from "@/api/queryKeys";

export function useCustomers(params: CustomerListParams) {
  return useQuery({
    queryKey: queryKeys.customers.list(params),
    queryFn: ({ signal }) => listCustomers(params, signal),
    // While page 3 loads, keep showing page 2 instead of flashing an empty table.
    placeholderData: keepPreviousData,
  });
}

export function useCustomer(id: string) {
  return useQuery({
    queryKey: queryKeys.customers.detail(id),
    queryFn: ({ signal }) => getCustomer(id, signal),
  });
}

/** After any write: put the fresh customer in the cache and refetch every list. */
function useStoreCustomer() {
  const queryClient = useQueryClient();
  return (customer: Customer) => {
    queryClient.setQueryData(queryKeys.customers.detail(customer.id), customer);
    // Lists may now be out of date (new row, changed name/status affects search,
    // filters and order), so mark them stale. Visible lists refetch right away.
    return queryClient.invalidateQueries({ queryKey: queryKeys.customers.lists() });
  };
}

export function useCreateCustomer() {
  const store = useStoreCustomer();
  return useMutation({ mutationFn: createCustomer, onSuccess: store });
}

export function useUpdateCustomer(id: string) {
  const store = useStoreCustomer();
  return useMutation({
    mutationFn: (input: CustomerUpdateInput) => updateCustomer(id, input),
    onSuccess: store,
  });
}

export function useSetCustomerActive(id: string) {
  const store = useStoreCustomer();
  return useMutation({
    mutationFn: (active: boolean) => (active ? reactivateCustomer(id) : deactivateCustomer(id)),
    onSuccess: store,
  });
}
