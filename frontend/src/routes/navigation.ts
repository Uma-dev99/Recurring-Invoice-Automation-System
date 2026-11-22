export interface NavItem {
  to: string;
  label: string;
  /**
   * Set only while the page is NOT built yet: the router then shows a placeholder
   * naming the roadmap phase that will implement it. Remove it when the page ships.
   */
  phase?: number;
}

export const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Dashboard" },
  { to: "/customers", label: "Customers" },
  { to: "/agreements", label: "Billing Agreements" },
  { to: "/invoices", label: "Invoices", phase: 5 },
  { to: "/jobs", label: "Failed / Pending Jobs", phase: 8 },
  { to: "/audit-logs", label: "Audit Logs", phase: 9 },
  { to: "/settings", label: "Settings", phase: 10 },
];
