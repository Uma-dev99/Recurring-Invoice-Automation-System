import { apiRequest } from "@/api/client";

export interface HealthStatus {
  status: "ok" | "unavailable";
  version: string;
  checks: Record<string, "ok" | "unavailable">;
}

export function fetchHealth(): Promise<HealthStatus> {
  return apiRequest<HealthStatus>("/health/");
}
