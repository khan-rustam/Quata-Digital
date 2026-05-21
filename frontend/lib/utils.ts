import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Locale-stable date formatter.
 *
 * Pinned to `en-GB` for two reasons:
 *  1. Cameroon (and most of the African readership) reads "4 Nov 2026",
 *     not the US "Nov 4, 2026".
 *  2. A fixed locale eliminates server-vs-client divergence — Next.js
 *     would otherwise render the server's `Intl` default and hydrate to
 *     the visitor's, triggering hydration mismatch warnings.
 *
 * Invalid inputs collapse to an empty string instead of leaking
 * "Invalid Date" into the UI.
 */
export function formatDate(input: string | Date | null | undefined): string {
  if (!input) return "";
  const d = typeof input === "string" ? new Date(input) : input;
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("en-GB", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}
