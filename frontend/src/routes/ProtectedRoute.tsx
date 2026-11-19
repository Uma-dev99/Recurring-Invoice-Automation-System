import { Navigate, Outlet, useLocation } from "react-router";

import { ErrorState } from "@/components/ui/ErrorState";
import { Spinner } from "@/components/ui/Spinner";
import { useCurrentUser } from "@/features/auth/hooks";

/**
 * Hides pages from anonymous users. Note: this is a UX convenience, NOT security.
 * Real protection is Django's IsAuthenticated permission on every endpoint; a user
 * who bypasses this component still gets 401 from the API.
 */
export function ProtectedRoute() {
  const location = useLocation();
  const { data: user, isPending, isError, refetch } = useCurrentUser();

  if (isPending) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner label="Loading session" />
      </div>
    );
  }
  if (isError) {
    return (
      <div className="flex h-full items-center justify-center">
        <ErrorState message="Could not verify your session." onRetry={() => refetch()} />
      </div>
    );
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <Outlet />;
}
