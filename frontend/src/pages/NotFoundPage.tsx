import { Link } from "react-router";

export function NotFoundPage() {
  return (
    <div className="flex min-h-full flex-col items-center justify-center gap-2 px-4">
      <p className="text-sm font-semibold text-slate-500">404</p>
      <h1 className="text-xl font-semibold text-slate-900">Page not found</h1>
      <Link to="/" className="text-sm font-medium text-slate-700 underline underline-offset-2">
        Back to dashboard
      </Link>
    </div>
  );
}
