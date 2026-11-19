import { createBrowserRouter } from "react-router";

import { AppLayout } from "@/layouts/AppLayout";
import { DashboardPage } from "@/pages/DashboardPage";
import { LoginPage } from "@/pages/LoginPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { PlaceholderPage } from "@/pages/PlaceholderPage";
import { NAV_ITEMS } from "@/routes/navigation";
import { ProtectedRoute } from "@/routes/ProtectedRoute";

const placeholderRoutes = NAV_ITEMS.filter((item) => item.to !== "/").map((item) => ({
  path: item.to.slice(1),
  element: <PlaceholderPage title={item.label} phase={item.phase} />,
}));

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  {
    element: <ProtectedRoute />,
    children: [
      {
        path: "/",
        element: <AppLayout />,
        children: [{ index: true, element: <DashboardPage /> }, ...placeholderRoutes],
      },
    ],
  },
  { path: "*", element: <NotFoundPage /> },
]);
