"use client";

import * as React from "react";
import { ChevronDown, HelpCircle } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";

export type FaqItem = {
  q: string;
  a: string;
};

const ease = [0.16, 1, 0.3, 1] as const;

export function FAQ({ items, defaultOpen = 0 }: { items: FaqItem[]; defaultOpen?: number | null }) {
  const [open, setOpen] = React.useState<number | null>(defaultOpen);

  return (
    <motion.div
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, margin: "-60px" }}
      variants={{
        hidden: {},
        show: { transition: { staggerChildren: 0.05 } },
      }}
      className="grid gap-3"
    >
      {items.map((item, i) => {
        const isOpen = open === i;
        return (
          <motion.div
            key={i}
            variants={{
              hidden: { opacity: 0, y: 12 },
              show: { opacity: 1, y: 0, transition: { duration: 0.45, ease } },
            }}
            className={cn(
              "rounded-2xl border bg-card transition-all",
              isOpen ? "border-primary/30 ring-soft" : "border-border hover:border-primary/20"
            )}
          >
            <button
              onClick={() => setOpen(isOpen ? null : i)}
              className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left cursor-pointer"
              aria-expanded={isOpen}
            >
              <span className="flex items-center gap-3">
                <HelpCircle
                  className={cn(
                    "h-4 w-4 shrink-0 transition-colors",
                    isOpen ? "text-primary" : "text-muted-foreground"
                  )}
                />
                <span className="text-sm font-medium">{item.q}</span>
              </span>
              <ChevronDown
                className={cn(
                  "h-4 w-4 text-muted-foreground transition-transform shrink-0",
                  isOpen && "rotate-180 text-primary"
                )}
              />
            </button>
            <AnimatePresence initial={false}>
              {isOpen && (
                <motion.div
                  key="content"
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.25, ease }}
                  className="overflow-hidden"
                >
                  <div className="px-5 pb-5 pt-0 text-sm text-muted-foreground border-t border-border/60 pl-12">
                    <div className="pt-3 whitespace-pre-line">{item.a}</div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        );
      })}
    </motion.div>
  );
}
