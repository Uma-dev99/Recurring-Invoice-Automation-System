import type { CustomerStatus, CustomerType } from "@/api/customers";
import type { StatusTone } from "@/components/ui/StatusBadge";

export const CUSTOMER_STATUS_LABEL: Record<CustomerStatus, string> = {
  ACTIVE: "Active",
  INACTIVE: "Inactive",
};

export const CUSTOMER_STATUS_TONE: Record<CustomerStatus, StatusTone> = {
  ACTIVE: "success",
  INACTIVE: "neutral",
};

export const CUSTOMER_TYPE_LABEL: Record<CustomerType, string> = {
  PERSON: "Person",
  COMPANY: "Company",
};
