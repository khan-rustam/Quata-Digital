import * as React from "react";
import type { LucideIcon } from "lucide-react";
import { MotionList, MotionItem } from "./motion-list";
import { cn } from "@/lib/utils";

export type StatTone =
  | "brand"
  | "amber"
  | "rose"
  | "sky"
  | "violet"
  | "emerald";

export type Stat = {
  value: string;
  label: string;
  hint?: string;
  icon?: LucideIcon;
  tone?: StatTone;
};

const toneStyles: Record<
  StatTone,
  { iconBg: string; iconText: string; ringHover: string; valueGradient: string }
> = {
  brand: {
    iconBg: "bg-brand-soft group-hover:bg-primary",
    iconText: "text-primary group-hover:text-white",
    ringHover: "group-hover:ring-primary/30",
    valueGradient: "from-primary to-emerald-500",
  },
  amber: {
    iconBg: "bg-amber-100 group-hover:bg-amber-500",
    iconText: "text-amber-700 group-hover:text-white",
    ringHover: "group-hover:ring-amber-400/40",
    valueGradient: "from-amber-600 to-orange-500",
  },
  rose: {
    iconBg: "bg-rose-100 group-hover:bg-rose-500",
    iconText: "text-rose-700 group-hover:text-white",
    ringHover: "group-hover:ring-rose-400/40",
    valueGradient: "from-rose-600 to-pink-500",
  },
  sky: {
    iconBg: "bg-sky-100 group-hover:bg-sky-500",
    iconText: "text-sky-700 group-hover:text-white",
    ringHover: "group-hover:ring-sky-400/40",
    valueGradient: "from-sky-600 to-cyan-500",
  },
  violet: {
    iconBg: "bg-violet-100 group-hover:bg-violet-500",
    iconText: "text-violet-700 group-hover:text-white",
    ringHover: "group-hover:ring-violet-400/40",
    valueGradient: "from-violet-600 to-fuchsia-500",
  },
  emerald: {
    iconBg: "bg-emerald-100 group-hover:bg-emerald-500",
    iconText: "text-emerald-700 group-hover:text-white",
    ringHover: "group-hover:ring-emerald-400/40",
    valueGradient: "from-emerald-600 to-teal-500",
  },
};

const defaultRotation: StatTone[] = ["brand", "amber", "sky", "violet", "rose", "emerald"];

export function StatStrip({
  items,
  columns = 4,
  variant = "card",
  className,
}: {
  items: Stat[];
  columns?: 2 | 3 | 4;
  variant?: "card" | "inline";
  className?: string;
}) {
  const cols = {
    2: "sm:grid-cols-2",
    3: "sm:grid-cols-3",
    4: "grid-cols-2 sm:grid-cols-4",
  }[columns];

  if (variant === "inline") {
    return (
      <MotionList className={cn("grid gap-y-6", cols, className)} staggerChildren={0.05}>
        {items.map((s, i) => {
          const tone = s.tone ?? defaultRotation[i % defaultRotation.length];
          const T = toneStyles[tone];
          const Icon = s.icon;
          return (
            <MotionItem key={i} y={8} duration={0.45}>
              <div className="text-center px-4">
                {Icon && (
                  <span
                    className={cn(
                      "mx-auto mb-2 inline-flex h-9 w-9 items-center justify-center rounded-xl transition-colors",
                      T.iconBg,
                      T.iconText
                    )}
                  >
                    <Icon className="h-4 w-4" />
                  </span>
                )}
                <div
                  className={cn(
                    "text-3xl md:text-4xl font-semibold tracking-tight bg-linear-to-br bg-clip-text text-transparent",
                    T.valueGradient
                  )}
                >
                  {s.value}
                </div>
                <div className="mt-1 text-sm font-medium">{s.label}</div>
                {s.hint && <div className="mt-1 text-xs text-muted-foreground">{s.hint}</div>}
              </div>
            </MotionItem>
          );
        })}
      </MotionList>
    );
  }

  return (
    <MotionList
      className={cn(
        "grid gap-3 sm:gap-px overflow-hidden sm:rounded-2xl sm:border sm:border-border sm:bg-border ring-soft",
        cols,
        className
      )}
      staggerChildren={0.06}
    >
      {items.map((s, i) => {
        const tone = s.tone ?? defaultRotation[i % defaultRotation.length];
        const T = toneStyles[tone];
        const Icon = s.icon;
        return (
          <MotionItem key={i} y={12}>
            <div
              className={cn(
                "group relative h-full bg-surface p-5 sm:p-7 flex flex-col gap-1.5 ring-soft sm:ring-0 rounded-2xl sm:rounded-none border sm:border-0 border-border",
                "transition-all duration-300 hover:bg-surface-soft cursor-default",
                "ring-0 hover:ring-2",
                T.ringHover
              )}
            >
              {/* Soft accent glow on hover */}
              <span
                aria-hidden
                className={cn(
                  "absolute -top-12 -right-12 h-28 w-28 rounded-full opacity-0 blur-2xl transition-opacity duration-500 group-hover:opacity-50 bg-linear-to-br",
                  T.valueGradient
                )}
              />

              <div className="relative flex items-center justify-between">
                <div
                  className={cn(
                    "text-2xl md:text-3xl font-semibold tracking-tight transition-all duration-300",
                    "group-hover:bg-linear-to-br group-hover:bg-clip-text group-hover:text-transparent",
                    T.valueGradient
                  )}
                >
                  {s.value}
                </div>
                {Icon && (
                  <span
                    className={cn(
                      "inline-flex h-9 w-9 items-center justify-center rounded-xl transition-all duration-300",
                      T.iconBg,
                      T.iconText,
                      "group-hover:scale-110 group-hover:-rotate-6 group-hover:shadow-md"
                    )}
                  >
                    <Icon className="h-4 w-4" />
                  </span>
                )}
              </div>
              <div className="relative text-xs uppercase tracking-wider text-muted-foreground">
                {s.label}
              </div>
              {s.hint && <div className="relative text-xs text-muted-foreground">{s.hint}</div>}
            </div>
          </MotionItem>
        );
      })}
    </MotionList>
  );
}
