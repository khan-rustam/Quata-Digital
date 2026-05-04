"use client";

import * as React from "react";
import { Check, Minus } from "lucide-react";
import { cn } from "@/lib/utils";

type Props = {
  checked: boolean;
  indeterminate?: boolean;
  onCheckedChange: (next: boolean) => void;
  ariaLabel?: string;
  className?: string;
};

export function Checkbox({ checked, indeterminate, onCheckedChange, ariaLabel, className }: Props) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={indeterminate ? "mixed" : checked}
      aria-label={ariaLabel}
      onClick={(e) => {
        e.stopPropagation();
        onCheckedChange(!checked);
      }}
      className={cn(
        "inline-flex h-4 w-4 items-center justify-center rounded border transition",
        checked || indeterminate
          ? "bg-primary border-primary text-primary-foreground"
          : "bg-surface border-border hover:border-primary/50",
        className
      )}
    >
      {indeterminate ? (
        <Minus className="h-3 w-3" />
      ) : checked ? (
        <Check className="h-3 w-3" />
      ) : null}
    </button>
  );
}
