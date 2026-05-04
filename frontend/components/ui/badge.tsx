import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors",
  {
    variants: {
      variant: {
        default: "border-transparent bg-secondary text-secondary-foreground",
        outline: "border-border text-foreground",
        brand: "border-transparent bg-brand-soft text-primary",
        accent: "border-transparent bg-accent/20 text-amber-900",
        success: "border-transparent bg-emerald-100 text-emerald-900",
        warn: "border-transparent bg-amber-100 text-amber-900",
        danger: "border-transparent bg-rose-100 text-rose-900",
        live: "border-emerald-200 bg-emerald-50 text-emerald-900",
        beta: "border-amber-200 bg-amber-50 text-amber-900",
        soon: "border-slate-200 bg-slate-50 text-slate-700",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
