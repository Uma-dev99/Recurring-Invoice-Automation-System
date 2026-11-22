import type { AgreementStatus } from "@/api/agreements";
import type { StatusTone } from "@/components/ui/StatusBadge";

export const AGREEMENT_STATUSES: AgreementStatus[] = ["ACTIVE", "PAUSED", "CANCELLED", "COMPLETED"];

export const AGREEMENT_STATUS_LABEL: Record<AgreementStatus, string> = {
  ACTIVE: "Active",
  PAUSED: "Paused",
  CANCELLED: "Cancelled",
  COMPLETED: "Completed",
};

export const AGREEMENT_STATUS_TONE: Record<AgreementStatus, StatusTone> = {
  ACTIVE: "success",
  PAUSED: "warning",
  CANCELLED: "neutral",
  COMPLETED: "info",
};

/** "12 months" / "1 month". */
export function formatCycles(cycles: number): string {
  return `${cycles} ${cycles === 1 ? "month" : "months"}`;
}
