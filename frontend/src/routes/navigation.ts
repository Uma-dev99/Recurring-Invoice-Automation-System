export interface NavItem {
  to: string;
  label: string;
  /** Roadmap phase that implements the page; shown on placeholder pages. */
  phase?: number;
}

export const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Dashboard" },
  { to: "/customers", label: "Customers", phase: 2 },
  { to: "/agreements", label: "Billing Agreements", phase: 3 },
  { to: "/invoices", label: "Invoices", phase: 5 },
  { to: "/jobs", label: "Failed / Pending Jobs", phase: 8 },
  { to: "/audit-logs", label: "Audit Logs", phase: 9 },
  { to: "/settings", label: "Settings", phase: 10 },
];
