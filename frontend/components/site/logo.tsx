import Image from "next/image";
import Link from "next/link";
import { cn } from "@/lib/utils";

const SIZE_CLASSES = {
  sm: "h-9",
  md: "h-12",
  lg: "h-14",
  xl: "h-20",
} as const;

/**
 * Rendered width in CSS px for each height above, derived from the lockup's
 * 3.87:1 ratio. Fed to `next/image` as `sizes` — without it the navbar asks
 * the optimiser for the full 1200px source to fill a 186px slot.
 */
const SIZE_WIDTHS: Record<keyof typeof SIZE_CLASSES, number> = {
  sm: 139,
  md: 186,
  lg: 217,
  xl: 310,
};

/**
 * QUATA Digital wordmark.
 *
 * The artwork is generated from `brand/header-lockup.png` into
 * `/public/brand/lockup.png` by `scripts/generate-favicons.mjs` — the teal QD
 * monogram, the QUATA DIGITAL wordmark and the tagline, in landscape
 * orientation. Never point this at the master in `brand/`: it is 6000px wide
 * and mostly transparent margin.
 *
 * We use the same asset on light and dark surfaces; on dark backgrounds we
 * lift it slightly with a subtle brightness so the gold reads at smaller
 * sizes.
 */
export function Logo({
  className,
  variant = "dark",
  size = "md",
  href = "/",
}: {
  className?: string;
  /** "dark" = on light surface (default).  "light" = on dark surface. */
  variant?: "dark" | "light";
  /** Visual size — md is the default for navbar, lg/xl for footer/hero. */
  size?: keyof typeof SIZE_CLASSES;
  href?: string;
}) {
  return (
    <Link
      href={href}
      aria-label="QUATA Digital home"
      className={cn("inline-flex items-center", className)}
    >
      <Image
        src="/brand/lockup.png"
        alt="QUATA Digital"
        width={1200}
        height={310}
        sizes={`${SIZE_WIDTHS[size]}px`}
        priority
        className={cn(
          "w-auto select-none",
          SIZE_CLASSES[size],
          variant === "light" ? "brightness-110" : ""
        )}
      />
    </Link>
  );
}
