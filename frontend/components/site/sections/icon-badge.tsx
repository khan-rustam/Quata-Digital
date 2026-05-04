import * as React from "react";
import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

const tones = {
  brand: "bg-brand-soft text-primary",
  amber: "bg-amber-100 text-amber-900",
  rose: "bg-rose-100 text-rose-900",
  sky: "bg-sky-100 text-sky-900",
  violet: "bg-violet-100 text-violet-900",
  emerald: "bg-emerald-100 text-emerald-900",
  ink: "bg-ink text-white",
  neutral: "bg-secondary text-foreground",
} as const;

const sizes = {
  sm: "h-8 w-8 [&_svg]:h-3.5 [&_svg]:w-3.5 rounded-lg",
  md: "h-10 w-10 [&_svg]:h-5 [&_svg]:w-5 rounded-xl",
  lg: "h-12 w-12 [&_svg]:h-5 [&_svg]:w-5 rounded-2xl",
  xl: "h-14 w-14 [&_svg]:h-6 [&_svg]:w-6 rounded-2xl",
} as const;

export function IconBadge({
  icon: Icon,
  tone = "brand",
  size = "md",
  className,
}: {
  icon: LucideIcon;
  tone?: keyof typeof tones;
  size?: keyof typeof sizes;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center justify-center shrink-0",
        tones[tone],
        sizes[size],
        className
      )}
    >
      <Icon />
    </span>
  );
}
