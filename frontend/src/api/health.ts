import { apiRequest } from "@/api/client";

/** "ok": a worker reported in the last few minutes; "stale": not recently; "unknown": never. */
export type WorkerStatus = "ok" | "stale" | "unknown";

export interface HealthStatus {
  status: "ok" | "unavailable";
  version: string;
  /** Readiness of this web instance (database, cache). Any failure means HTTP 503. */
  checks: Record<string, "ok" | "unavailable">;
  /** Informational only: never makes the endpoint fail. */
  background: { workers: WorkerStatus };
}

export function fetchHealth(): Promise<HealthStatus> {
  return apiRequest<HealthStatus>("/health/");
}
