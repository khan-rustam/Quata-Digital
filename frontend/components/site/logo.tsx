import Link from "next/link";
import { cn } from "@/lib/utils";

export function Logo({
  className,
  variant = "dark",
}: {
  className?: string;
  variant?: "dark" | "light";
}) {
  const ink = variant === "dark" ? "text-ink" : "text-white";
  return (
    <Link
      href="/"
      className={cn("group inline-flex items-center gap-2", className)}
    >
      <span className="relative inline-flex h-7 w-7 items-center justify-center rounded-lg gradient-brand text-white">
        <svg viewBox="0 0 24 24" className="h-4 w-4" aria-hidden>
          <path
            d="M4 12a8 8 0 1 1 14 5.4L20 20l-4-1.6A8 8 0 0 1 4 12Z"
            fill="white"
            opacity="0.95"
          />
          <circle cx="12" cy="12" r="3" fill="#0E5B4A" />
        </svg>
      </span>
      <span className={cn("font-semibold tracking-tight text-[15px]", ink)}>
        QUATA<span className="text-primary">.</span>
      </span>
    </Link>
  );
}
