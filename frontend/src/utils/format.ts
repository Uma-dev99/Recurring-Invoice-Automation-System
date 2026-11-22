/**
 * Display formatting. These functions only DISPLAY values; the frontend never computes
 * amounts or billing dates that are saved or sent anywhere (the backend owns that).
 */

const LOCALE = "nl-NL";

/**
 * "49.95" (the API sends money as strings) -> "€ 49,95".
 * Converting to Number is fine for display: up to billions, 2-decimal values are shown
 * exactly. Never use the converted number for arithmetic.
 */
export function formatMoney(amount: string, currency = "EUR"): string {
  return new Intl.NumberFormat(LOCALE, { style: "currency", currency }).format(Number(amount));
}

/**
 * "2027-01-31" (a calendar day, no time) -> "31 jan 2027".
 * Don't use `new Date("2027-01-31")`: JavaScript reads it as midnight UTC, which shows
 * as 30 January in any time zone west of UTC. Build the date from its parts instead.
 */
export function formatDay(isoDay: string): string {
  const [year, month, day] = isoDay.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString(LOCALE, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/** A timestamp from the API ("2027-01-15T10:22:03Z") in the viewer's local time. */
export function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString(LOCALE, { dateStyle: "medium", timeStyle: "short" });
}

/** Today's date as "YYYY-MM-DD" in the viewer's time zone (for date-input minimums). */
export function todayIsoDay(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}
