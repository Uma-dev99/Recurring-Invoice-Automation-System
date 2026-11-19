import { ApiError, apiRequest } from "@/api/client";
import type { LoginInput } from "@/schemas/auth";

export interface CurrentUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  is_staff: boolean;
}

/** Ensures the csrftoken cookie exists before the first unsafe request (login). */
export function fetchCsrfCookie(): Promise<void> {
  return apiRequest<void>("/auth/csrf/");
}

/** Returns the logged-in user, or null when the session is missing/expired. */
export async function fetchCurrentUser(): Promise<CurrentUser | null> {
  try {
    return await apiRequest<CurrentUser>("/auth/me/");
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}

export async function login(credentials: LoginInput): Promise<CurrentUser> {
  await fetchCsrfCookie();
  return apiRequest<CurrentUser>("/auth/login/", { method: "POST", body: credentials });
}

export function logout(): Promise<void> {
  return apiRequest<void>("/auth/logout/", { method: "POST" });
}
