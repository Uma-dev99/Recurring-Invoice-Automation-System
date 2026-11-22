/**
 * Small helpers for the in-browser demo backend.
 *
 * Dates are "YYYY-MM-DD" strings (calendar days), money is "49.95" strings, exactly like
 * the real API. Money is added up in whole cents so no cent is ever lost to rounding.
 */

/** A date "days" days from today, as YYYY-MM-DD (the viewer's own calendar). */
export function dayOffset(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return isoDay(d);
}

export function isoDay(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function today(): string {
  return dayOffset(0);
}

function parseDay(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

/** Same rule as backend apps/billing/schedule.add_months: clamp to the month's last day. */
export function addMonths(iso: string, months: number): string {
  const day = parseDay(iso);
  const monthIndex = day.getMonth() + months;
  const year = day.getFullYear() + Math.floor(monthIndex / 12);
  const month = ((monthIndex % 12) + 12) % 12;
  const lastDay = new Date(year, month + 1, 0).getDate();
  return isoDay(new Date(year, month, Math.min(day.getDate(), lastDay)));
}

export function addDays(iso: string, days: number): string {
  const d = parseDay(iso);
  d.setDate(d.getDate() + days);
  return isoDay(d);
}

/** Month n (1-based) of a schedule: always counted from the anchor; ends the day before the next. */
export function periodDates(anchor: string, cycle: number): { start: string; end: string } {
  const start = addMonths(anchor, cycle - 1);
  const end = addDays(addMonths(anchor, cycle), -1);
  return { start, end };
}

export function toCents(amount: string): number {
  return Math.round(Number(amount) * 100);
}

export function fromCents(cents: number): string {
  return (cents / 100).toFixed(2);
}

export function sumAmounts(amounts: string[]): string {
  return fromCents(amounts.reduce((total, a) => total + toCents(a), 0));
}

export function uuid(): string {
  return crypto.randomUUID();
}

/** An ISO timestamp at a given hour on a calendar day (local time). */
export function timestampOn(iso: string, hour = 9, minute = 0): string {
  const d = parseDay(iso);
  d.setHours(hour, minute, 0, 0);
  return d.toISOString();
}

export function nowIso(): string {
  return new Date().toISOString();
}
