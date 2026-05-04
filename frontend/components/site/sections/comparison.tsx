"use client";

import { Check, X } from "lucide-react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

type Row = { label: string; quata: string | boolean; standalone: string | boolean };

const ease = [0.16, 1, 0.3, 1] as const;

export function ComparisonTable({
  rows,
  leftLabel = "Standalone tools",
  rightLabel = "QUATA ecosystem",
}: {
  rows: Row[];
  leftLabel?: string;
  rightLabel?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.55, ease }}
      className="overflow-hidden rounded-2xl border border-border bg-card ring-soft"
    >
      <div className="grid grid-cols-[1.4fr_1fr_1fr] sm:grid-cols-3 bg-surface-soft text-[10px] sm:text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        <div className="p-3 sm:p-4">Capability</div>
        <div className="p-3 sm:p-4 text-center">{leftLabel}</div>
        <div className="p-3 sm:p-4 text-center bg-brand-soft text-primary">{rightLabel}</div>
      </div>
      <motion.ul
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, margin: "-60px" }}
        variants={{
          hidden: {},
          show: { transition: { staggerChildren: 0.04, delayChildren: 0.1 } },
        }}
        className="divide-y divide-border"
      >
        {rows.map((r, i) => (
          <motion.li
            key={i}
            variants={{
              hidden: { opacity: 0, x: -8 },
              show: { opacity: 1, x: 0, transition: { duration: 0.4, ease } },
            }}
            className="grid grid-cols-[1.4fr_1fr_1fr] sm:grid-cols-3 text-xs sm:text-sm hover:bg-surface-soft/40 transition-colors"
          >
            <div className="p-3 sm:p-4 font-medium">{r.label}</div>
            <Cell value={r.standalone} />
            <Cell value={r.quata} highlight />
          </motion.li>
        ))}
      </motion.ul>
    </motion.div>
  );
}

function Cell({ value, highlight }: { value: string | boolean; highlight?: boolean }) {
  return (
    <div
      className={cn(
        "p-3 sm:p-4 text-center",
        highlight && "bg-brand-soft/30"
      )}
    >
      {typeof value === "boolean" ? (
        value ? (
          <Check className={cn("inline h-4 w-4", highlight ? "text-primary" : "text-muted-foreground")} />
        ) : (
          <X className="inline h-4 w-4 text-muted-foreground/60" />
        )
      ) : (
        <span className={cn("text-xs sm:text-sm", highlight ? "text-foreground font-medium" : "text-muted-foreground")}>
          {value}
        </span>
      )}
    </div>
  );
}
