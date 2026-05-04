/**
 * Light client-side validation helpers.
 *
 * Backend stays the source of truth; these provide instant feedback so users
 * don't have to round-trip to the server for obvious mistakes.
 */

export function isEmail(v: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v.trim());
}

export function isPhone(v: string): boolean {
  // Permissive — accepts +234 (0) 700 0000, +44-20-7946-0958, 0123456789, etc.
  const digits = v.replace(/[^\d]/g, "");
  return digits.length >= 7 && digits.length <= 15;
}

export function isUrl(v: string): boolean {
  try {
    const u = new URL(v.trim());
    return u.protocol === "http:" || u.protocol === "https:";
  } catch {
    return false;
  }
}

export function isSlug(v: string): boolean {
  return /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(v.trim());
}

export type FieldError = string | null;

export function validateField(name: string, value: string, opts: {
  required?: boolean;
  type?: "text" | "email" | "tel" | "url" | "slug";
} = {}): FieldError {
  const v = value?.trim() ?? "";
  if (opts.required && !v) return "Required";
  if (!v) return null;
  switch (opts.type) {
    case "email":
      return isEmail(v) ? null : "Enter a valid email";
    case "tel":
      return isPhone(v) ? null : "Enter a valid phone number";
    case "url":
      return isUrl(v) ? null : "Enter a valid URL (https://…)";
    case "slug":
      return isSlug(v) ? null : "Use lowercase letters, numbers and hyphens";
    default:
      return null;
  }
}
