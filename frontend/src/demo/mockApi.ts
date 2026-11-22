/**
 * An in-browser stand-in for the Django API, used only in the portfolio demo build.
 *
 * Same paths, same response shapes and the same error envelope ({"error": {code,
 * message, details}}, 401/404/409/422) as the real backend, and the key business rules:
 * agreement lifecycle and version conflicts, "can't deactivate a customer with live
 * agreements", invoice operator actions including the Riverty safety check, and an
 * audit entry for every change. It is deliberately simpler than the backend (no real
 * concurrency, lighter validation): the forms validate in the browser already.
 */
import { ApiError, type Paginated } from "@/api/client";
import type { AgreementStatus } from "@/api/agreements";
import type { InvoiceAction, InvoiceStatus } from "@/api/invoices";

import {
  type AgreementRow,
  type CustomerRow,
  type InvoiceRow,
  type PeriodRow,
  DEMO_USER,
  audit,
  db,
  save,
} from "./store";
import { addDays, fromCents, nowIso, periodDates, sumAmounts, toCents, today, uuid } from "./util";

type Query = Record<string, string>;
interface Req {
  method: string;
  path: string;
  query: Query;
  body: Record<string, unknown>;
}
type Handler = (req: Req, params: string[]) => unknown;

const routes: [string, RegExp, Handler][] = [];
function route(method: string, pattern: string, handler: Handler) {
  const regex = new RegExp(`^${pattern.replaceAll(":id", "([0-9a-f-]{36})")}$`);
  routes.push([method, regex, handler]);
}

export async function handleDemoRequest<T>(
  path: string,
  method: string,
  query: Record<string, unknown> | undefined,
  body: unknown,
): Promise<T> {
  // A short pause, so loading states look like a real network round trip.
  await new Promise((resolve) => setTimeout(resolve, 120 + Math.random() * 180));
  const cleanQuery: Query = {};
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null && value !== "") cleanQuery[key] = String(value);
  }
  const req: Req = { method, path, query: cleanQuery, body: (body as Record<string, unknown>) ?? {} };

  const publicPath = path.startsWith("/auth/csrf") || path.startsWith("/auth/login") || path.startsWith("/health");
  if (!publicPath && !db().loggedIn) {
    throw new ApiError(401, "not_authenticated", "Authentication credentials were not provided.");
  }
  for (const [m, regex, handler] of routes) {
    const match = regex.exec(path);
    if (match && m === method) {
      const result = handler(req, match.slice(1));
      if (method !== "GET") save();
      return result as T;
    }
  }
  throw new ApiError(404, "not_found", "Not found.");
}

// --- helpers -----------------------------------------------------------------------------------

function notFound(): never {
  throw new ApiError(404, "not_found", "Not found.");
}

function fieldError(field: string, message: string): never {
  throw new ApiError(400, "validation_error", "Invalid input.", { [field]: [message] });
}

function domainError(code: string, message: string, details: Record<string, unknown> = {}, status = 422): never {
  throw new ApiError(status, code, message, details);
}

function paginate<T>(items: T[], query: Query): Paginated<T> {
  const pageSize = Math.min(Number(query.page_size) || 25, 100);
  const page = Number(query.page) || 1;
  const totalPages = Math.max(1, Math.ceil(items.length / pageSize));
  if (page > totalPages && page > 1) throw new ApiError(404, "not_found", "Invalid page.");
  return {
    count: items.length,
    page,
    page_size: pageSize,
    total_pages: totalPages,
    next: page < totalPages ? `?page=${page + 1}` : null,
    previous: page > 1 ? `?page=${page - 1}` : null,
    results: items.slice((page - 1) * pageSize, page * pageSize),
  };
}

function sortBy<T>(items: T[], ordering: string, fields: Record<string, (item: T) => string | number>): T[] {
  const descending = ordering.startsWith("-");
  const key = fields[ordering.replace(/^-/, "")];
  if (!key) return items;
  return [...items].sort((a, b) => {
    const x = key(a);
    const y = key(b);
    const result = x < y ? -1 : x > y ? 1 : 0;
    return descending ? -result : result;
  });
}

function contains(value: string, term: string): boolean {
  return value.toLowerCase().includes(term.toLowerCase());
}

const customer = (id: string) => db().customers.find((c) => c.id === id) ?? notFound();
const agreement = (id: string) => db().agreements.find((a) => a.id === id) ?? notFound();
const period = (id: string) => db().periods.find((p) => p.id === id) ?? notFound();
const invoice = (id: string) => db().invoices.find((i) => i.id === id) ?? notFound();
const periodsOf = (agreementId: string) =>
  db().periods.filter((p) => p.agreement_id === agreementId).sort((a, b) => a.cycle_number - b.cycle_number);

function touch(row: { updated_at: string }) {
  row.updated_at = nowIso();
}

// --- serializers (same shapes as the real API) ---------------------------------------------

function agreementOut(a: AgreementRow) {
  const c = customer(a.customer_id);
  const { customer_id: _customerId, ...rest } = a;
  return {
    ...rest,
    customer: { id: c.id, name: c.name, external_customer_id: c.external_customer_id, status: c.status },
  };
}

function periodOut(p: PeriodRow) {
  const { agreement_id: _agreementId, ...rest } = p;
  return rest;
}

const ACTIONS: Partial<Record<InvoiceStatus, InvoiceAction[]>> = {
  REJECTED: ["retry", "cancel"],
  NEEDS_ATTENTION: ["retry", "mark_received", "cancel"],
  UNKNOWN: ["retry", "mark_received", "cancel"],
};

function mayExistAtRiverty(i: InvoiceRow): boolean {
  return i.attempts.at(-1)?.outcome === "UNKNOWN";
}

function invoiceOut(i: InvoiceRow, detail = false) {
  const p = period(i.period_id);
  const a = agreement(p.agreement_id);
  const c = customer(a.customer_id);
  const { period_id: _periodId, attempts, ...rest } = i;
  const base = {
    ...rest,
    period: { id: p.id, cycle_number: p.cycle_number, period_start: p.period_start, period_end: p.period_end },
    agreement: { id: a.id, description: a.description },
    customer: { id: c.id, name: c.name },
  };
  if (!detail) return base;
  return {
    ...base,
    attempts,
    available_actions: ACTIONS[i.status] ?? [],
    may_exist_at_riverty: mayExistAtRiverty(i),
  };
}

// --- auth and health -----------------------------------------------------------------------

route("GET", "/auth/csrf/", () => undefined);
route("POST", "/auth/login/", (req) => {
  if (!req.body.email || !req.body.password) fieldError("password", "Enter any email and password.");
  db().loggedIn = true;
  return DEMO_USER;
});
route("POST", "/auth/logout/", () => {
  db().loggedIn = false;
  return undefined;
});
route("GET", "/auth/me/", () => DEMO_USER);
route("GET", "/health/", () => ({
  status: "ok",
  version: "demo",
  checks: { database: "ok", cache: "ok" },
  background: { workers: "ok" },
}));

// --- customers -------------------------------------------------------------------------------

const EDITABLE_CUSTOMER_FIELDS = [
  "customer_type",
  "name",
  "email",
  "phone",
  "address_line1",
  "address_line2",
  "postal_code",
  "city",
  "country_code",
] as const;

route("GET", "/customers/", (req) => {
  const { search, status, customer_type, ordering = "name" } = req.query;
  let items = db().customers.filter(
    (c) =>
      (!search || contains(c.name, search) || contains(c.external_customer_id, search) || contains(c.email, search)) &&
      (!status || c.status === status) &&
      (!customer_type || c.customer_type === customer_type),
  );
  items = sortBy(items, ordering, {
    name: (c) => c.name.toLowerCase(),
    external_customer_id: (c) => c.external_customer_id,
    created_at: (c) => c.created_at,
  });
  return paginate(items, req.query);
});

route("POST", "/customers/", (req) => {
  const external = String(req.body.external_customer_id ?? "").trim();
  if (db().customers.some((c) => c.external_customer_id === external)) {
    fieldError("external_customer_id", "A customer with this external customer id already exists.");
  }
  const now = nowIso();
  const row: CustomerRow = {
    id: uuid(),
    external_customer_id: external,
    customer_type: "PERSON",
    name: "",
    email: "",
    phone: "",
    address_line1: "",
    address_line2: "",
    postal_code: "",
    city: "",
    country_code: "",
    status: "ACTIVE",
    created_at: now,
    updated_at: now,
  };
  for (const field of EDITABLE_CUSTOMER_FIELDS) {
    if (req.body[field] !== undefined) (row as unknown as Record<string, unknown>)[field] = String(req.body[field]).trim();
  }
  row.country_code = row.country_code.toUpperCase();
  db().customers.push(row);
  audit("customer.created", "customers.customer", row.id, { name: row.name, external_customer_id: external });
  return row;
});

route("GET", "/customers/:id/", (_req, [id]) => customer(id));

route("PATCH", "/customers/:id/", (req, [id]) => {
  const row = customer(id);
  const changes: Record<string, unknown> = {};
  for (const field of EDITABLE_CUSTOMER_FIELDS) {
    if (req.body[field] === undefined) continue;
    let value = String(req.body[field]).trim();
    if (field === "country_code") value = value.toUpperCase();
    if (row[field] !== value) {
      changes[field] = { old: row[field], new: value };
      (row as unknown as Record<string, unknown>)[field] = value;
    }
  }
  if (Object.keys(changes).length) {
    touch(row);
    audit("customer.updated", "customers.customer", row.id, changes);
  }
  return row;
});

route("POST", "/customers/:id/deactivate/", (_req, [id]) => {
  const row = customer(id);
  if (row.status === "INACTIVE") domainError("customer_already_inactive", "This customer is already inactive.");
  const live = db().agreements.some((a) => a.customer_id === id && (a.status === "ACTIVE" || a.status === "PAUSED"));
  if (live) domainError("customer_has_live_agreements", "This customer has active or paused agreements. Cancel them first.");
  row.status = "INACTIVE";
  touch(row);
  audit("customer.deactivated", "customers.customer", row.id, { status: { old: "ACTIVE", new: "INACTIVE" } });
  return row;
});

route("POST", "/customers/:id/reactivate/", (_req, [id]) => {
  const row = customer(id);
  if (row.status === "ACTIVE") domainError("customer_already_active", "This customer is already active.");
  row.status = "ACTIVE";
  touch(row);
  audit("customer.reactivated", "customers.customer", row.id, { status: { old: "INACTIVE", new: "ACTIVE" } });
  return row;
});

// --- agreements --------------------------------------------------------------------------------

route("GET", "/agreements/", (req) => {
  const { customer: customerId, status, search, ordering = "-created_at" } = req.query;
  let items = db().agreements.filter((a) => {
    const c = customer(a.customer_id);
    return (
      (!customerId || a.customer_id === customerId) &&
      (!status || a.status === status) &&
      (!search || contains(a.description, search) || contains(c.name, search) || contains(c.external_customer_id, search))
    );
  });
  items = sortBy(items, ordering, {
    created_at: (a) => a.created_at,
    anchor_date: (a) => a.anchor_date,
    amount: (a) => toCents(a.amount),
  });
  const page = paginate(items, req.query);
  return { ...page, results: page.results.map(agreementOut) };
});

route("POST", "/agreements/", (req) => {
  const c = customer(String(req.body.customer_id));
  if (c.status !== "ACTIVE") domainError("customer_not_active", "Agreements can only be created for active customers.");
  const anchor = String(req.body.anchor_date);
  if (anchor < today()) fieldError("anchor_date", "The first billing date cannot be in the past.");
  const cycles = Number(req.body.total_cycles ?? 12);
  const now = nowIso();
  const row: AgreementRow = {
    id: uuid(),
    customer_id: c.id,
    description: String(req.body.description).trim(),
    amount: fromCents(toCents(String(req.body.amount))),
    currency: "EUR",
    anchor_date: anchor,
    total_cycles: cycles,
    status: "ACTIVE",
    cancelled_at: null,
    version: 1,
    created_at: now,
    updated_at: now,
  };
  db().agreements.push(row);
  for (let cycle = 1; cycle <= cycles; cycle++) {
    const { start, end } = periodDates(anchor, cycle);
    db().periods.push({
      id: uuid(),
      agreement_id: row.id,
      cycle_number: cycle,
      period_start: start,
      period_end: end,
      amount: row.amount,
      currency: "EUR",
      status: "SCHEDULED",
    });
  }
  audit("agreement.created", "agreements.billingagreement", row.id, {
    description: row.description,
    amount: row.amount,
    anchor_date: anchor,
    total_cycles: cycles,
    periods_generated: cycles,
  });
  return agreementOut(row);
});

route("GET", "/agreements/:id/", (_req, [id]) => agreementOut(agreement(id)));
route("GET", "/agreements/:id/periods/", (_req, [id]) => periodsOf(agreement(id).id).map(periodOut));

function lockVersion(a: AgreementRow, version: unknown) {
  if (Number(version) !== a.version) {
    domainError(
      "agreement_version_conflict",
      "This agreement was changed by someone else. Reload it and try again.",
      { expected_version: Number(version), current_version: a.version },
      409,
    );
  }
}

function requireOpen(a: AgreementRow) {
  if (a.status === "CANCELLED" || a.status === "COMPLETED") {
    domainError("agreement_closed", `A ${a.status.toLowerCase()} agreement can no longer be changed.`);
  }
}

route("PATCH", "/agreements/:id/", (req, [id]) => {
  const a = agreement(id);
  lockVersion(a, req.body.version);
  requireOpen(a);
  const description = req.body.description === undefined ? a.description : String(req.body.description).trim();
  if (description !== a.description) {
    audit("agreement.updated", "agreements.billingagreement", a.id, { description: { old: a.description, new: description } });
    a.description = description;
    a.version += 1;
    touch(a);
  }
  return agreementOut(a);
});

const TRANSITIONS: Record<string, { from: AgreementStatus[]; to: AgreementStatus; past: string }> = {
  pause: { from: ["ACTIVE"], to: "PAUSED", past: "paused" },
  resume: { from: ["PAUSED"], to: "ACTIVE", past: "resumed" },
  cancel: { from: ["ACTIVE", "PAUSED"], to: "CANCELLED", past: "cancelled" },
};

for (const action of Object.keys(TRANSITIONS)) {
  route("POST", `/agreements/:id/${action}/`, (req, [id]) => {
    const a = agreement(id);
    lockVersion(a, req.body.version);
    const rule = TRANSITIONS[action];
    if (!rule.from.includes(a.status)) {
      const label = a.status.toLowerCase();
      domainError("invalid_agreement_transition", `${/^[aeiou]/.test(label) ? "An" : "A"} ${label} agreement cannot be ${rule.past}.`);
    }
    const changes: Record<string, unknown> = { status: { old: a.status, new: rule.to } };
    const periods = periodsOf(a.id);
    if (a.status === "PAUSED" && action !== "pause") {
      // Months that fell due while paused are skipped, never billed later.
      const due = periods.filter((p) => p.status === "SCHEDULED" && p.period_start <= today());
      due.forEach((p) => (p.status = "SKIPPED"));
      changes.periods_skipped = due.length;
    }
    if (action === "cancel") {
      const open = periods.filter((p) => p.status === "SCHEDULED");
      open.forEach((p) => (p.status = "CANCELLED"));
      changes.periods_cancelled = open.length;
      a.cancelled_at = nowIso();
      const reason = String(req.body.reason ?? "").trim();
      if (reason) changes.reason = reason;
    }
    a.status = rule.to;
    a.version += 1;
    touch(a);
    audit(`agreement.${rule.past}`, "agreements.billingagreement", a.id, changes);
    return agreementOut(a);
  });
}

route("POST", "/agreements/:id/change-amount/", (req, [id]) => {
  const a = agreement(id);
  lockVersion(a, req.body.version);
  requireOpen(a);
  const fromCycle = Number(req.body.from_cycle);
  if (!(fromCycle >= 1 && fromCycle <= a.total_cycles)) fieldError("from_cycle", `Choose a month between 1 and ${a.total_cycles}.`);
  const inRange = periodsOf(a.id).filter((p) => p.cycle_number >= fromCycle);
  const locked = inRange.find((p) => p.status === "INVOICING" || p.status === "INVOICED");
  if (locked) {
    domainError("periods_already_invoiced", `Month ${locked.cycle_number} is already invoiced. Choose a later month.`, {
      first_invoiced_cycle: locked.cycle_number,
    });
  }
  const amount = fromCents(toCents(String(req.body.amount)));
  const scheduled = inRange.filter((p) => p.status === "SCHEDULED");
  if (!scheduled.length) domainError("no_unbilled_periods", `No months from month ${fromCycle} onwards can still be billed.`);
  scheduled.forEach((p) => (p.amount = amount));
  audit("agreement.amount_changed", "agreements.billingagreement", a.id, {
    amount: { old: a.amount, new: amount },
    from_cycle: fromCycle,
    periods_repriced: scheduled.length,
  });
  a.amount = amount;
  a.version += 1;
  touch(a);
  return agreementOut(a);
});

// --- invoices ----------------------------------------------------------------------------------

route("GET", "/invoices/", (req) => {
  const { status, agreement: agreementId, search, stuck, ordering = "-created_at" } = req.query;
  if (stuck === "true") return paginate([], req.query);
  let items = db().invoices.filter((i) => {
    const p = period(i.period_id);
    const a = agreement(p.agreement_id);
    return (
      (!status || i.status === status) &&
      (!agreementId || a.id === agreementId) &&
      (!search ||
        contains(i.merchant_reference, search) ||
        contains(i.external_invoice_id, search) ||
        contains(a.description, search) ||
        contains(customer(a.customer_id).name, search))
    );
  });
  items = sortBy(items, ordering, {
    created_at: (i) => i.created_at,
    period_start: (i) => period(i.period_id).period_start,
  });
  const page = paginate(items, req.query);
  return { ...page, results: page.results.map((i) => invoiceOut(i)) };
});

route("GET", "/invoices/:id/", (_req, [id]) => invoiceOut(invoice(id), true));

function operatorCheck(i: InvoiceRow, body: Record<string, unknown>, action: InvoiceAction): string {
  if (body.expected_status !== i.status) {
    domainError(
      "invoice_changed",
      "This invoice changed while you were looking at it. Reload and check again.",
      { expected_status: body.expected_status, current_status: i.status },
      409,
    );
  }
  if (!(ACTIONS[i.status] ?? []).includes(action)) {
    domainError("action_not_allowed", `This action isn't possible for an invoice that is ${i.status.toLowerCase()}.`);
  }
  const reason = String(body.reason ?? "").trim();
  if (reason.length < 5) fieldError("reason", "Explain briefly why (it is kept in the audit log).");
  return reason;
}

function requireRivertyCheck(i: InvoiceRow, confirmed: unknown) {
  if (mayExistAtRiverty(i) && confirmed !== true) {
    domainError(
      "riverty_check_required",
      "The last attempt got no clear answer, so Riverty may already have this invoice. Check with Riverty first, then confirm it does not exist there.",
    );
  }
}

route("POST", "/invoices/:id/retry/", (req, [id]) => {
  const i = invoice(id);
  const reason = operatorCheck(i, req.body, "retry");
  requireRivertyCheck(i, req.body.confirmed_not_at_riverty);
  i.status = "RETRY_SCHEDULED";
  i.next_attempt_at = nowIso();
  touch(i);
  audit("invoice.operator_retried", "invoicing.invoicesubmission", i.id, { status: i.status, reason });
  return invoiceOut(i, true);
});

route("POST", "/invoices/:id/mark-received/", (req, [id]) => {
  const i = invoice(id);
  const reason = operatorCheck(i, req.body, "mark_received");
  const number = String(req.body.external_invoice_id ?? "").trim();
  if (!number) fieldError("external_invoice_id", "Enter Riverty's invoice number.");
  accept(i, number);
  audit("invoice.operator_marked_received", "invoicing.invoicesubmission", i.id, { status: "ACCEPTED", reason, external_invoice_id: number });
  return invoiceOut(i, true);
});

route("POST", "/invoices/:id/cancel/", (req, [id]) => {
  const i = invoice(id);
  const reason = operatorCheck(i, req.body, "cancel");
  requireRivertyCheck(i, req.body.confirmed_not_at_riverty);
  i.status = "CANCELLED";
  i.next_attempt_at = null;
  touch(i);
  period(i.period_id).status = "SKIPPED";
  audit("invoice.operator_cancelled", "invoicing.invoicesubmission", i.id, { status: i.status, reason });
  return invoiceOut(i, true);
});

function accept(i: InvoiceRow, externalId: string) {
  i.status = "ACCEPTED";
  i.external_invoice_id = externalId;
  i.accepted_at = nowIso();
  i.next_attempt_at = null;
  i.last_error_category = "";
  i.last_error_message = "";
  touch(i);
  const p = period(i.period_id);
  p.status = "INVOICED";
  const a = agreement(p.agreement_id);
  const open = periodsOf(a.id).some((x) => x.status === "SCHEDULED" || x.status === "INVOICING");
  if (!open && (a.status === "ACTIVE" || a.status === "PAUSED")) {
    audit("agreement.completed", "agreements.billingagreement", a.id, { status: { old: a.status, new: "COMPLETED" } }, { system: true });
    a.status = "COMPLETED";
    a.version += 1;
  }
}

// --- attention (Failed / pending jobs) -----------------------------------------------------------

function missedPeriods(): PeriodRow[] {
  return db()
    .periods.filter((p) => p.status === "SCHEDULED" && p.period_end < today() && agreement(p.agreement_id).status === "ACTIVE")
    .sort((a, b) => a.period_end.localeCompare(b.period_end));
}

function attentionSummary() {
  const count = (status: InvoiceStatus) => db().invoices.filter((i) => i.status === status).length;
  const summary = {
    needs_attention: count("NEEDS_ATTENTION"),
    rejected: count("REJECTED"),
    unknown: count("UNKNOWN"),
    stuck: 0,
    missed_periods: missedPeriods().length,
    failed_events: db().failedEvents.length,
    retry_scheduled: count("RETRY_SCHEDULED"),
  };
  return {
    ...summary,
    total:
      summary.needs_attention + summary.rejected + summary.unknown + summary.missed_periods + summary.failed_events,
  };
}

route("GET", "/attention/summary/", () => attentionSummary());

route("GET", "/attention/missed-periods/", (req) => {
  const page = paginate(missedPeriods(), req.query);
  return {
    ...page,
    results: page.results.map((p) => {
      const a = agreement(p.agreement_id);
      const c = customer(a.customer_id);
      return { ...periodOut(p), agreement: { id: a.id, description: a.description }, customer: { id: c.id, name: c.name } };
    }),
  };
});

function requireReason(body: Record<string, unknown>): string {
  const reason = String(body.reason ?? "").trim();
  if (reason.length < 5) fieldError("reason", "Explain briefly why (it is kept in the audit log).");
  return reason;
}

route("POST", "/attention/missed-periods/:id/invoice-now/", (req, [id]) => {
  const reason = requireReason(req.body);
  const p = period(id);
  createInvoice(p);
  audit("period.operator_invoiced", "billing.billingperiod", p.id, { reason });
  return periodOut(p);
});

route("POST", "/attention/missed-periods/:id/skip/", (req, [id]) => {
  const reason = requireReason(req.body);
  const p = period(id);
  p.status = "SKIPPED";
  audit("period.operator_skipped", "billing.billingperiod", p.id, { reason, cycle_number: p.cycle_number });
  return periodOut(p);
});

route("GET", "/attention/failed-events/", (req) => paginate(db().failedEvents, req.query));

route("POST", "/attention/failed-events/:id/requeue/", (req, [id]) => {
  const reason = requireReason(req.body);
  const event = db().failedEvents.find((e) => e.id === id) ?? notFound();
  db().failedEvents = db().failedEvents.filter((e) => e.id !== id);
  audit("outbox.operator_requeued", "operations.outboxevent", event.id, { reason, event_type: event.event_type, previous_error: event.last_error });
  return { ...event, attempts: 0, last_error: "" };
});

// --- dashboard and audit log -------------------------------------------------------------------

route("GET", "/dashboard/", () => {
  const now = today();
  const monthStart = `${now.slice(0, 8)}01`;
  const monthEnd = addDays(periodDates(monthStart, 2).start, -1);
  const figure = (amounts: string[]) => ({ count: amounts.length, amount: sumAmounts(amounts) });
  const inMonth = db().periods.filter(
    (p) => p.period_start >= monthStart && p.period_start <= monthEnd && ["SCHEDULED", "INVOICING", "INVOICED"].includes(p.status),
  );
  const accepted = db().invoices.filter(
    (i) => i.status === "ACCEPTED" && i.accepted_at && i.accepted_at.slice(0, 10) >= monthStart && i.accepted_at.slice(0, 10) <= monthEnd,
  );
  const upcoming = db().periods.filter(
    (p) =>
      p.status === "SCHEDULED" &&
      p.period_start > now &&
      p.period_start <= addDays(now, 7) &&
      agreement(p.agreement_id).status === "ACTIVE",
  );
  return {
    as_of: now,
    month_start: monthStart,
    month_end: monthEnd,
    active_agreements: db().agreements.filter((a) => a.status === "ACTIVE").length,
    paused_agreements: db().agreements.filter((a) => a.status === "PAUSED").length,
    month_scheduled: figure(inMonth.map((p) => p.amount)),
    month_invoiced: figure(inMonth.filter((p) => p.status === "INVOICED").map((p) => p.amount)),
    month_open: figure(inMonth.filter((p) => p.status !== "INVOICED").map((p) => p.amount)),
    accepted_this_month: figure(accepted.map((i) => i.amount)),
    upcoming: figure(upcoming.map((p) => p.amount)),
    upcoming_days: 7,
    needs_attention: attentionSummary().total,
  };
});

route("GET", "/audit-logs/", (req) => {
  const { action, entity_type, entity_id, actor, date_from, date_to } = req.query;
  const items = db().audit.filter(
    (e) =>
      (!action || e.action === action) &&
      (!entity_type || e.entity_type === entity_type) &&
      (!entity_id || e.entity_id === entity_id) &&
      (!actor || (actor === "system" ? e.actor === null : e.actor?.id === actor)) &&
      (!date_from || e.created_at.slice(0, 10) >= date_from) &&
      (!date_to || e.created_at.slice(0, 10) <= date_to),
  );
  return paginate(items, req.query);
});

route("GET", "/audit-logs/filters/", () => ({
  actions: [...new Set(db().audit.map((e) => e.action))].sort(),
  entity_types: [...new Set(db().audit.map((e) => e.entity_type))].sort(),
}));

// --- the simulated billing run (the demo banner's button) -------------------------------------

function createInvoice(p: PeriodRow): InvoiceRow {
  const a = agreement(p.agreement_id);
  const now = nowIso();
  const row: InvoiceRow = {
    id: uuid(),
    period_id: p.id,
    merchant_reference: `AGR-${a.id.replaceAll("-", "").slice(0, 12).toUpperCase()}-C${String(p.cycle_number).padStart(3, "0")}`,
    status: "PENDING",
    amount: p.amount,
    currency: "EUR",
    external_invoice_id: "",
    attempt_count: 0,
    next_attempt_at: null,
    accepted_at: null,
    last_error_category: "",
    last_error_message: "",
    created_at: now,
    updated_at: now,
    attempts: [],
  };
  p.status = "INVOICING";
  db().invoices.push(row);
  audit("invoice.submission_created", "invoicing.invoicesubmission", row.id, { merchant_reference: row.merchant_reference, amount: row.amount }, { system: true });
  return row;
}

/**
 * What the Celery jobs do every hour, in one click: invoice the months that are due and
 * send pending/retrying invoices to the (fake) Riverty. Markers in an agreement's
 * description choose Riverty's answer, like the backend's FakeGateway:
 * "[reject]", "[retry]", "[timeout]"; anything else is accepted.
 */
export function runBillingCycle(): { created: number; sent: number } {
  const now = today();
  let created = 0;
  for (const p of db().periods) {
    const a = agreement(p.agreement_id);
    if (p.status === "SCHEDULED" && a.status === "ACTIVE" && p.period_start <= now && p.period_end >= now) {
      createInvoice(p);
      created += 1;
    }
  }
  const toSend = db().invoices.filter((i) => i.status === "PENDING" || i.status === "RETRY_SCHEDULED");
  for (const i of toSend) {
    const description = agreement(period(i.period_id).agreement_id).description.toLowerCase();
    const started = nowIso();
    const outcome = description.includes("[reject]")
      ? "REJECTED"
      : description.includes("[retry]")
        ? "RETRYABLE"
        : description.includes("[timeout]")
          ? "UNKNOWN"
          : "ACCEPTED";
    const message = {
      REJECTED: "Fake Riverty: the customer's postal address is invalid.",
      RETRYABLE: "Fake Riverty: service temporarily unavailable (503).",
      UNKNOWN: "Fake Riverty: no response within 10 seconds.",
      ACCEPTED: "",
    }[outcome];
    i.attempts.push({
      attempt_number: i.attempts.length + 1,
      outcome,
      error_category: outcome === "ACCEPTED" ? "" : outcome.toLowerCase(),
      error_message: message,
      request_summary: { merchant_reference: i.merchant_reference, amount: i.amount, currency: "EUR" },
      response_summary: outcome === "ACCEPTED" ? { http_status: 201 } : {},
      started_at: started,
      finished_at: nowIso(),
    });
    i.attempt_count = i.attempts.length;
    if (outcome === "ACCEPTED") {
      accept(i, `RIV-${Math.floor(200000 + Math.random() * 99999)}`);
    } else {
      i.status = outcome === "RETRYABLE" ? (i.attempt_count >= 5 ? "NEEDS_ATTENTION" : "RETRY_SCHEDULED") : (outcome as InvoiceStatus);
      i.last_error_category = outcome.toLowerCase();
      i.last_error_message = message;
      i.next_attempt_at = i.status === "RETRY_SCHEDULED" ? new Date(Date.now() + 60_000 * 2 ** i.attempt_count).toISOString() : null;
      touch(i);
    }
    audit(`invoice.${i.status.toLowerCase()}`, "invoicing.invoicesubmission", i.id, { status: i.status, attempt_count: i.attempt_count }, { system: true });
  }
  save();
  return { created, sent: toSend.length };
}

