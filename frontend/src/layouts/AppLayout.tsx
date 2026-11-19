import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router";

import { useCurrentUser, useLogout } from "@/features/auth/hooks";
import { NAV_ITEMS } from "@/routes/navigation";
import { cn } from "@/utils/cn";

export function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex h-full">
      {/* Sidebar: static on desktop, slide-over on tablet/mobile */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-30 w-64 border-r border-slate-200 bg-white transition-transform lg:static lg:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex h-14 items-center border-b border-slate-200 px-5">
          <span className="text-sm font-semibold tracking-tight text-slate-900">Invoice Automation</span>
        </div>
        <nav className="space-y-0.5 p-3" aria-label="Main">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              onClick={() => setSidebarOpen(false)}
              className={({ isActive }) =>
                cn(
                  "block rounded-md px-3 py-2 text-sm font-medium",
                  isActive ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      {sidebarOpen && (
        <div
          className="fixed inset-0 z-20 bg-slate-900/30 lg:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onMenuClick={() => setSidebarOpen(true)} />
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function Topbar({ onMenuClick }: { onMenuClick: () => void }) {
  const { data: user } = useCurrentUser();
  const logout = useLogout();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout.mutate(undefined, { onSettled: () => navigate("/login", { replace: true }) });
  };

  return (
    <header className="flex h-14 items-center justify-between border-b border-slate-200 bg-white px-4 lg:px-6">
      <button
        type="button"
        onClick={onMenuClick}
        className="rounded-md border border-slate-200 px-2.5 py-1 text-sm text-slate-600 lg:hidden"
        aria-label="Open navigation"
      >
        Menu
      </button>
      <div className="hidden lg:block" />
      <div className="flex items-center gap-4">
        {/* Real notifications arrive with operational alerts in Phase 9. */}
        <span className="hidden text-sm text-slate-400 sm:inline" title="Available in Phase 9">
          Notifications
        </span>
        <div className="text-right">
          <p className="text-sm font-medium text-slate-900">{user?.full_name}</p>
          <p className="text-xs text-slate-500">{user?.email}</p>
        </div>
        <button
          type="button"
          onClick={handleLogout}
          disabled={logout.isPending}
          className="rounded-md border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        >
          Sign out
        </button>
      </div>
    </header>
  );
}
