/** GET /api/v1/dashboard/: every figure is computed by the backend; we only display it. */
import { apiRequest } from "@/api/client";

/** A count with the total amount behind it. Amount is a string ("1249.95"): exact. */
export interface Figure {
  count: number;
  amount: string;
}

export interface DashboardKpis {
  as_of: string;
  month_start: string;
  month_end: string;
  active_agreements: number;
  paused_agreements: number;
  /** Months starting this month that are meant to be billed. */
  month_scheduled: Figure;
  month_invoiced: Figure;
  month_open: Figure;
  /** Accepted by Riverty during this month (accepted is not paid). */
  accepted_this_month: Figure;
  upcoming: Figure;
  upcoming_days: number;
  needs_attention: number;
}

export function getDashboard(signal?: AbortSignal) {
  return apiRequest<DashboardKpis>("/dashboard/", { signal });
}
