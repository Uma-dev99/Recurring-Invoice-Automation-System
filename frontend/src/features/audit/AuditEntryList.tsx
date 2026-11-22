import { Link } from "react-router";

import type { AuditEntry } from "@/api/auditLogs";
import { actionLabel, changeText, recordLink, recordName } from "@/features/audit/format";
import { formatTimestamp } from "@/utils/format";

/**
 * Audit entries as a readable list: when, who, what, and what changed.
 * Shared by the Audit logs page, the dashboard's recent activity and History panels.
 */
export function AuditEntryList({
  entries,
  showRecord = true,
  compact = false,
}: {
  entries: AuditEntry[];
  /** Show which record each entry is about (off inside a record's own History panel). */
  showRecord?: boolean;
  /** Hide the changes (dashboard). */
  compact?: boolean;
}) {
  return (
    <ol className="divide-y divide-slate-100">
      {entries.map((entry) => {
        const link = recordLink(entry.entity_type, entry.entity_id);
        const changes = Object.entries(entry.changes);
        return (
          <li key={entry.id} className="px-4 py-3 text-sm">
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className="font-medium text-slate-900">{actionLabel(entry.action)}</span>
              {showRecord && (
                <span className="text-slate-600">
                  {recordName(entry.entity_type)}
                  {link && (
                    <>
                      {" · "}
                      <Link to={link} className="font-mono text-xs hover:underline">
                        {entry.entity_id.slice(0, 8)}
                      </Link>
                    </>
                  )}
                </span>
              )}
              <span className="text-xs text-slate-500">
                {entry.actor ? entry.actor.full_name : "System"} · {formatTimestamp(entry.created_at)}
              </span>
            </div>
            {!compact && changes.length > 0 && (
              <dl className="mt-1 grid grid-cols-1 gap-x-3 text-xs sm:grid-cols-[max-content_1fr]">
                {changes.map(([field, value]) => (
                  <div key={field} className="contents">
                    <dt className="text-slate-500">{field.replaceAll("_", " ")}</dt>
                    <dd className="break-words text-slate-800">{changeText(value)}</dd>
                  </div>
                ))}
              </dl>
            )}
          </li>
        );
      })}
    </ol>
  );
}
