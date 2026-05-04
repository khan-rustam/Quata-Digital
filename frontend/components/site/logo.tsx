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
 * QUATA Digital wordmark.
 *
 * The artwork lives at `/public/logo.png` — a gold-on-transparent
 * hexagon mark + wordmark, in landscape orientation. We use the same
 * asset on light and dark surfaces; on dark backgrounds we lift it
 * slightly with a subtle brightness so the gold reads at smaller sizes.
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
        src="/logo.png"
        alt="QUATA Digital"
        width={840}
        height={600}
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
