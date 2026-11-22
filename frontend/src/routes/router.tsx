import { createBrowserRouter } from "react-router";

import { AppLayout } from "@/layouts/AppLayout";
import { AgreementDetailPage } from "@/pages/agreements/AgreementDetailPage";
import { AgreementNewPage } from "@/pages/agreements/AgreementNewPage";
import { AgreementsPage } from "@/pages/agreements/AgreementsPage";
import { CustomerDetailPage } from "@/pages/customers/CustomerDetailPage";
import { CustomerNewPage } from "@/pages/customers/CustomerNewPage";
import { CustomersPage } from "@/pages/customers/CustomersPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { InvoiceDetailPage } from "@/pages/invoices/InvoiceDetailPage";
import { InvoicesPage } from "@/pages/invoices/InvoicesPage";
import { JobsPage } from "@/pages/jobs/JobsPage";
import { LoginPage } from "@/pages/LoginPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { PlaceholderPage } from "@/pages/PlaceholderPage";
import { NAV_ITEMS } from "@/routes/navigation";
import { ProtectedRoute } from "@/routes/ProtectedRoute";

// Pages that are not built yet (they still carry a roadmap phase in NAV_ITEMS).
const placeholderRoutes = NAV_ITEMS.filter((item) => item.phase !== undefined).map((item) => ({
  path: item.to.slice(1),
  element: <PlaceholderPage title={item.label} phase={item.phase} />,
}));

const customerRoutes = [
  { path: "customers", element: <CustomersPage /> },
  // "new" is matched before ":customerId", so it is never treated as an id.
  { path: "customers/new", element: <CustomerNewPage /> },
  { path: "customers/:customerId", element: <CustomerDetailPage /> },
];

const agreementRoutes = [
  { path: "agreements", element: <AgreementsPage /> },
  { path: "agreements/new", element: <AgreementNewPage /> },
  { path: "agreements/:agreementId", element: <AgreementDetailPage /> },
];

const invoiceRoutes = [
  { path: "invoices", element: <InvoicesPage /> },
  { path: "invoices/:invoiceId", element: <InvoiceDetailPage /> },
  { path: "jobs", element: <JobsPage /> },
];

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  {
    element: <ProtectedRoute />,
    children: [
      {
        path: "/",
        element: <AppLayout />,
        children: [
          { index: true, element: <DashboardPage /> },
          ...customerRoutes,
          ...agreementRoutes,
          ...invoiceRoutes,
          ...placeholderRoutes,
        ],
      },
    ],
  },
  { path: "*", element: <NotFoundPage /> },
]);
