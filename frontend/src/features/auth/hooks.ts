import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchCurrentUser, login, logout } from "@/api/auth";
import { queryKeys } from "@/api/queryKeys";

/** Server state "who am I?". `data === null` means not logged in. */
export function useCurrentUser() {
  return useQuery({
    queryKey: queryKeys.auth.me,
    queryFn: fetchCurrentUser,
    staleTime: 5 * 60_000,
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: login,
    onSuccess: (user) => {
      // Seed the cache with the response instead of refetching /me.
      queryClient.setQueryData(queryKeys.auth.me, user);
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: logout,
    onSettled: () => {
      // Drop every cached record so the next user never sees the previous user's data.
      queryClient.clear();
      queryClient.setQueryData(queryKeys.auth.me, null);
    },
  });
}
