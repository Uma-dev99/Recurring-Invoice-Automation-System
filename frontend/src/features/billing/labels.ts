import type { PeriodStatus } from "@/api/billing";
import type { StatusTone } from "@/components/ui/StatusBadge";

export const PERIOD_STATUS_LABEL: Record<PeriodStatus, string> = {
  SCHEDULED: "Scheduled",
  INVOICING: "Invoicing",
  INVOICED: "Invoiced",
  SKIPPED: "Skipped",
  CANCELLED: "Cancelled",
};

export const PERIOD_STATUS_TONE: Record<PeriodStatus, StatusTone> = {
  SCHEDULED: "neutral",
  INVOICING: "info",
  INVOICED: "success",
  SKIPPED: "warning",
  CANCELLED: "neutral",
};

/** Months that are being or have been invoiced: their price can never change again. */
export const LOCKED_STATUSES: PeriodStatus[] = ["INVOICING", "INVOICED"];
