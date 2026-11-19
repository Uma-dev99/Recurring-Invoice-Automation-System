import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";

import { ApiError } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";

function handleUnauthorized(error: unknown) {
  // Session expired mid-use: mark the user as logged out. ProtectedRoute
  // observes this cache entry and redirects to /login.
  if (error instanceof ApiError && error.status === 401) {
    queryClient.setQueryData(queryKeys.auth.me, null);
  }
}

export const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: handleUnauthorized }),
  mutationCache: new MutationCache({ onError: handleUnauthorized }),
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: true,
      // Retrying a 4xx is pointless (the request itself is wrong); retry network/5xx twice.
      retry: (failureCount, error) => {
        if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false;
        return failureCount < 2;
      },
    },
    mutations: {
      // Never auto-retry writes: retrying a non-idempotent POST could duplicate it.
      retry: false,
    },
  },
});
