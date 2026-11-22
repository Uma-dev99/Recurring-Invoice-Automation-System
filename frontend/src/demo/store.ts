/**
 * The demo's "database": plain objects in the browser, saved to localStorage so a
 * visitor's changes survive a page reload. Reset restores the sample data.
 *
 * The sample history is built relative to TODAY, so the demo always looks current:
 * months in the past are invoiced, this month is due, future months are scheduled, and
 * a few invoices show each problem the Failed / pending jobs screen handles.
 */
import type { Agreement } from "@/api/agreements";
import type { AuditEntry } from "@/api/auditLogs";
import type { FailedEvent } from "@/api/attention";
import type { BillingPeriod } from "@/api/billing";
import type { Customer } from "@/api/customers";
import type { InvoiceDetail, InvoiceStatus, ProcessingAttempt } from "@/api/invoices";

import { addDays, dayOffset, periodDates, timestampOn, today, uuid } from "./util";

export type CustomerRow = Customer;
export type AgreementRow = Omit<Agreement, "customer"> & { customer_id: string };
export type PeriodRow = BillingPeriod & { agreement_id: string };
export type InvoiceRow = Omit<
  InvoiceDetail,
  "period" | "agreement" | "customer" | "available_actions" | "may_exist_at_riverty"
> & { period_id: string };

export interface DemoState {
  schema: 1;
  loggedIn: boolean;
  customers: CustomerRow[];
  agreements: AgreementRow[];
  periods: PeriodRow[];
  invoices: InvoiceRow[];
  audit: AuditEntry[];
  failedEvents: FailedEvent[];
}

export const DEMO_USER = {
  id: "00000000-0000-4000-8000-000000000001",
  email: "demo@portfolio.dev",
  first_name: "Demo",
  last_name: "Operator",
  full_name: "Demo Operator",
  is_staff: true,
};
const ACTOR = { id: DEMO_USER.id, email: DEMO_USER.email, full_name: DEMO_USER.full_name };
const STORAGE_KEY = "invoice-automation-demo";

let state: DemoState | null = null;

export function db(): DemoState {
  if (!state) state = load() ?? seed();
  return state;
}

export function save(): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(db()));
  } catch {
    /* private mode or storage full: the demo still works for this page view */
  }
}

export function resetDemo(): void {
  const loggedIn = db().loggedIn;
  state = seed();
  state.loggedIn = loggedIn;
  save();
}

function load(): DemoState | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? (JSON.parse(raw) as DemoState) : null;
    return parsed?.schema === 1 ? parsed : null;
  } catch {
    return null;
  }
}

export function audit(
  action: string,
  entityType: string,
  entityId: string,
  changes: Record<string, unknown>,
  options: { system?: boolean; at?: string } = {},
): void {
  db().audit.unshift({
    id: uuid(),
    created_at: options.at ?? new Date().toISOString(),
    action,
    entity_type: entityType,
    entity_id: entityId,
    actor: options.system ? null : ACTOR,
    changes,
  });
}

// --- sample data ---------------------------------------------------------------------------

interface AgreementSpec {
  customer: string; // external id
  description: string;
  amount: string;
  startsInDays: number; // negative = started in the past
  cycles: number;
  status?: Agreement["status"];
  /** Problem invoices for given months (1-based); other started months get accepted. */
  problems?: Record<number, InvoiceStatus>;
  /** Started months that were never invoiced (to show "missed months"). */
  missed?: number[];
}

const CUSTOMERS: Omit<CustomerRow, "id" | "created_at" | "updated_at">[] = [
  company("DEMO-0001", "Acme Facilities B.V.", "billing@acme-facilities.example", "Oudegracht 120", "3511 AX", "Utrecht", "NL"),
  person("DEMO-0002", "Jan de Vries", "jan.devries@mail.example", "Prinsengracht 263", "1016 GV", "Amsterdam", "NL"),
  person("DEMO-0003", "Sophie Martens", "sophie.martens@mail.example", "Meir 50", "2000", "Antwerpen", "BE"),
  company("DEMO-0004", "Bakkerij Smit", "administratie@bakkerijsmit.example", "Nieuwe Binnenweg 77", "3014 GC", "Rotterdam", "NL"),
  person("DEMO-0005", "Lukas Weber", "lukas.weber@mail.example", "Hohe Straße 12", "50667", "Köln", "DE"),
  company("DEMO-0006", "Nordic Design Studio", "finance@nordicdesign.example", "Herengracht 410", "1017 BX", "Amsterdam", "NL"),
  company("DEMO-0007", "Van der Berg Consultancy", "facturen@vdberg.example", "Lange Voorhout 9", "2514 EA", "Den Haag", "NL"),
  { ...company("DEMO-0008", "Old Harbour Logistics", "finance@oldharbour.example", "Hoge der A 4", "9712 AC", "Groningen", "NL"), status: "INACTIVE" },
];

const AGREEMENTS: AgreementSpec[] = [
  { customer: "DEMO-0001", description: "Facility management, Gold plan", amount: "249.00", startsInDays: -150, cycles: 12 },
  { customer: "DEMO-0001", description: "Support add-on", amount: "39.95", startsInDays: -65, cycles: 6, status: "PAUSED" },
  { customer: "DEMO-0002", description: "Streaming Plus", amount: "12.99", startsInDays: -95, cycles: 12, problems: { 4: "UNKNOWN" } },
  { customer: "DEMO-0003", description: "Fitness membership", amount: "29.50", startsInDays: -120, cycles: 12, status: "CANCELLED" },
  { customer: "DEMO-0004", description: "Point-of-sale software licence", amount: "59.00", startsInDays: -40, cycles: 24, problems: { 2: "REJECTED" } },
  { customer: "DEMO-0005", description: "Magazine subscription", amount: "7.95", startsInDays: 3, cycles: 12 },
  { customer: "DEMO-0006", description: "Design tools, Team plan", amount: "119.00", startsInDays: -38, cycles: 12, problems: { 2: "NEEDS_ATTENTION" } },
  { customer: "DEMO-0007", description: "Cloud backup", amount: "19.50", startsInDays: -70, cycles: 12, missed: [2], problems: { 3: "RETRY_SCHEDULED" } },
  { customer: "DEMO-0008", description: "Fleet tracking", amount: "120.00", startsInDays: -200, cycles: 12, status: "CANCELLED" },
  // Healthy ones whose latest month began a few days ago, so "this month" has accepted invoices.
  { customer: "DEMO-0007", description: "Accounting software, Pro", amount: "89.00", startsInDays: -186, cycles: 12 },
  { customer: "DEMO-0004", description: "Payroll service", amount: "45.00", startsInDays: -125, cycles: 12 },
  { customer: "DEMO-0006", description: "Coworking desk", amount: "210.00", startsInDays: -63, cycles: 6 },
];

function seed(): DemoState {
  state = { schema: 1, loggedIn: false, customers: [], agreements: [], periods: [], invoices: [], audit: [], failedEvents: [] };
  const byExternalId = new Map<string, CustomerRow>();

  CUSTOMERS.forEach((spec, index) => {
    const createdDay = dayOffset(-210 + index * 3);
    const row: CustomerRow = {
      ...spec,
      id: uuid(),
      created_at: timestampOn(createdDay, 10),
      updated_at: timestampOn(createdDay, 10),
    };
    state!.customers.push(row);
    byExternalId.set(row.external_customer_id, row);
    audit("customer.created", "customers.customer", row.id, { name: row.name, external_customer_id: row.external_customer_id }, { at: row.created_at });
  });

  for (const spec of AGREEMENTS) seedAgreement(spec, byExternalId.get(spec.customer)!);

  // One background job that gave up, for the "Failed background jobs" tab.
  state.failedEvents.push({
    id: uuid(),
    event_type: "invoice.submit",
    payload: { submission_id: uuid() },
    attempts: 8,
    last_error: "ConnectionError: Riverty sandbox unreachable (DNS lookup failed)",
    created_at: timestampOn(dayOffset(-2), 6, 5),
    available_at: timestampOn(dayOffset(-1), 23, 40),
  });

  state.audit.sort((a, b) => b.created_at.localeCompare(a.created_at));
  return state;
}

function seedAgreement(spec: AgreementSpec, customer: CustomerRow): void {
  const s = state!;
  const anchor = dayOffset(spec.startsInDays);
  const created = timestampOn(addDays(anchor, -7), 11);
  const status = spec.status ?? "ACTIVE";
  const agreement: AgreementRow = {
    id: uuid(),
    customer_id: customer.id,
    description: spec.description,
    amount: spec.amount,
    currency: "EUR",
    anchor_date: anchor,
    total_cycles: spec.cycles,
    status,
    cancelled_at: status === "CANCELLED" ? timestampOn(dayOffset(-30), 14) : null,
    version: status === "ACTIVE" ? 1 : 2,
    created_at: created,
    updated_at: created,
  };
  s.agreements.push(agreement);
  audit("agreement.created", "agreements.billingagreement", agreement.id, {
    description: agreement.description,
    amount: agreement.amount,
    anchor_date: anchor,
    total_cycles: spec.cycles,
    periods_generated: spec.cycles,
  }, { at: created });

  const now = today();
  for (let cycle = 1; cycle <= spec.cycles; cycle++) {
    const { start, end } = periodDates(anchor, cycle);
    const started = start <= now;
    const period: PeriodRow = {
      id: uuid(),
      agreement_id: agreement.id,
      cycle_number: cycle,
      period_start: start,
      period_end: end,
      amount: spec.amount,
      currency: "EUR",
      status: "SCHEDULED",
    };
    s.periods.push(period);

    const cancelledBefore = status === "CANCELLED" && agreement.cancelled_at && start > agreement.cancelled_at.slice(0, 10);
    if (cancelledBefore) {
      period.status = "CANCELLED";
    } else if (status === "PAUSED" && started && cycle > 1) {
      period.status = "SKIPPED";
    } else if (spec.missed?.includes(cycle)) {
      period.status = "SCHEDULED"; // window passed without an invoice: a "missed month"
    } else if (started) {
      const problem = spec.problems?.[cycle];
      period.status = problem ? "INVOICING" : "INVOICED";
      seedInvoice(period, problem ?? "ACCEPTED");
    } else if (status === "CANCELLED") {
      period.status = "CANCELLED";
    }
  }

  if (status === "PAUSED") audit("agreement.paused", "agreements.billingagreement", agreement.id, { status: { old: "ACTIVE", new: "PAUSED" } }, { at: timestampOn(dayOffset(-20), 15) });
  if (status === "CANCELLED") audit("agreement.cancelled", "agreements.billingagreement", agreement.id, { status: { old: "ACTIVE", new: "CANCELLED" }, reason: "Customer ended the contract" }, { at: agreement.cancelled_at! });
}

function seedInvoice(period: PeriodRow, status: InvoiceStatus): void {
  const s = state!;
  const reference = `AGR-${period.agreement_id.replaceAll("-", "").slice(0, 12).toUpperCase()}-C${String(period.cycle_number).padStart(3, "0")}`;
  const sentAt = timestampOn(period.period_start, 6, 5);
  const attempts: ProcessingAttempt[] = [];
  const attempt = (outcome: ProcessingAttempt["outcome"], error_category = "", error_message = "", minutes = 0) =>
    attempts.push({
      attempt_number: attempts.length + 1,
      outcome,
      error_category,
      error_message,
      request_summary: { merchant_reference: reference, amount: period.amount, currency: "EUR", cycle_number: period.cycle_number },
      response_summary: outcome === "ACCEPTED" ? { http_status: 201 } : {},
      started_at: new Date(Date.parse(sentAt) + minutes * 60_000).toISOString(),
      finished_at: new Date(Date.parse(sentAt) + minutes * 60_000 + 640).toISOString(),
    });

  const invoice: InvoiceRow = {
    id: uuid(),
    period_id: period.id,
    merchant_reference: reference,
    status,
    amount: period.amount,
    currency: "EUR",
    external_invoice_id: "",
    attempt_count: 0,
    next_attempt_at: null,
    accepted_at: null,
    last_error_category: "",
    last_error_message: "",
    created_at: sentAt,
    updated_at: sentAt,
    attempts,
  };

  if (status === "ACCEPTED") {
    attempt("ACCEPTED");
    invoice.external_invoice_id = `RIV-${String(100000 + s.invoices.length * 7 + period.cycle_number).slice(0, 6)}`;
    invoice.accepted_at = attempts[0].finished_at;
  } else if (status === "REJECTED") {
    attempt("REJECTED", "validation", "Riverty: the customer's postal address could not be validated.");
  } else if (status === "UNKNOWN") {
    attempt("UNKNOWN", "read_timeout", "No response from Riverty within 10 seconds.");
  } else if (status === "RETRY_SCHEDULED") {
    attempt("RETRYABLE", "service_unavailable", "Riverty: service temporarily unavailable (503).");
    invoice.next_attempt_at = new Date(Date.now() + 25 * 60_000).toISOString();
  } else if (status === "NEEDS_ATTENTION") {
    for (let i = 0; i < 5; i++) attempt("RETRYABLE", "service_unavailable", "Riverty: service temporarily unavailable (503).", 2 ** i);
    invoice.last_error_message = "Gave up after 5 attempts. Riverty: service temporarily unavailable (503).";
  }
  invoice.attempt_count = attempts.length;
  const last = attempts[attempts.length - 1];
  if (status !== "ACCEPTED" && !invoice.last_error_message) invoice.last_error_message = last.error_message;
  if (status !== "ACCEPTED") invoice.last_error_category = last.error_category;
  invoice.updated_at = last.finished_at ?? sentAt;
  s.invoices.push(invoice);

  audit(`invoice.${status.toLowerCase()}`, "invoicing.invoicesubmission", invoice.id, {
    status,
    attempt_count: invoice.attempt_count,
    ...(invoice.external_invoice_id ? { external_invoice_id: invoice.external_invoice_id } : {}),
    ...(invoice.last_error_message ? { error: invoice.last_error_message } : {}),
  }, { system: true, at: invoice.updated_at });
}

function company(id: string, name: string, email: string, address: string, postal: string, city: string, country: string) {
  return base(id, "COMPANY", name, email, address, postal, city, country);
}

function person(id: string, name: string, email: string, address: string, postal: string, city: string, country: string) {
  return base(id, "PERSON", name, email, address, postal, city, country);
}

function base(
  external_customer_id: string,
  customer_type: Customer["customer_type"],
  name: string,
  email: string,
  address_line1: string,
  postal_code: string,
  city: string,
  country_code: string,
): Omit<CustomerRow, "id" | "created_at" | "updated_at"> {
  return {
    external_customer_id,
    customer_type,
    name,
    email,
    phone: "",
    address_line1,
    address_line2: "",
    postal_code,
    city,
    country_code,
    status: "ACTIVE",
  };
}
