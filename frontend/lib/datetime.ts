/**
 * Hydration-safe date/time formatters.
 *
 * `Date#toLocaleString` uses the running environment's default locale,
 * which differs server-side (Node, usually `en-US`) and client-side
 * (visitor's OS / browser). That mismatch produces React hydration
 * warnings and visibly flickers numbers/months when the page
 * rehydrates.
 *
 * Pinning to a fixed locale eliminates both problems. We use `en-GB`
 * because the bulk of the QUATA audience is in Africa, where day-month
 * ordering is the local convention.
 */

const DATE_TIME_FMT = new Intl.DateTimeFormat("en-GB", {
  year: "numeric",
  month: "short",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
  timeZone: "UTC",
});

const DATE_FMT = new Intl.DateTimeFormat("en-GB", {
  year: "numeric",
  month: "short",
  day: "2-digit",
  timeZone: "UTC",
});

const TIME_FMT = new Intl.DateTimeFormat("en-GB", {
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
  timeZone: "UTC",
});

function parse(input: string | Date | null | undefined): Date | null {
  if (!input) return null;
  const d = typeof input === "string" ? new Date(input) : input;
  return Number.isNaN(d.getTime()) ? null : d;
}

export function formatDateTime(input: string | Date | null | undefined): string {
  const d = parse(input);
  return d ? DATE_TIME_FMT.format(d) : "";
}

export function formatDateShort(input: string | Date | null | undefined): string {
  const d = parse(input);
  return d ? DATE_FMT.format(d) : "";
}

export function formatTimeShort(input: string | Date | null | undefined): string {
  const d = parse(input);
  return d ? TIME_FMT.format(d) : "";
}
