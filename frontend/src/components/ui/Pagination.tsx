interface PaginationProps {
  page: number;
  totalPages: number;
  count: number;
  onPageChange: (page: number) => void;
  /** True while the next page loads; the previous page stays visible meanwhile. */
  isFetching?: boolean;
}

/** Previous/next controls for the backend's StandardPagination responses. */
export function Pagination({ page, totalPages, count, onPageChange, isFetching }: PaginationProps) {
  const pages = Math.max(totalPages, 1);
  const buttonClass =
    "rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50";

  return (
    <nav
      className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 px-4 py-3 text-sm"
      aria-label="Pagination"
    >
      <p className="text-slate-600 tabular-nums">
        {count} {count === 1 ? "result" : "results"} · page {page} of {pages}
        {isFetching && <span className="ml-2 text-slate-400">Loading…</span>}
      </p>
      <div className="flex gap-2">
        <button type="button" className={buttonClass} disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
          Previous
        </button>
        <button type="button" className={buttonClass} disabled={page >= pages} onClick={() => onPageChange(page + 1)}>
          Next
        </button>
      </div>
    </nav>
  );
}
