"use client";

import { motion } from "framer-motion";

const items = [
  "Featured in TechCabal",
  "Disrupt Africa",
  "Quartz Africa",
  "Rest of World",
  "BusinessDay",
  "Africa Insider",
];

const ease = [0.16, 1, 0.3, 1] as const;

export function PressStrip() {
  return (
    <motion.div
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, margin: "-60px" }}
      variants={{
        hidden: {},
        show: { transition: { staggerChildren: 0.04 } },
      }}
    >
      <div className="text-center text-xs uppercase tracking-wider text-muted-foreground">
        As featured in
      </div>
      <div className="mt-6 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3 sm:gap-4 items-center">
        {items.map((name) => (
          <motion.div
            key={name}
            variants={{
              hidden: { opacity: 0, y: 8 },
              show: { opacity: 1, y: 0, transition: { duration: 0.4, ease } },
            }}
            className="flex items-center justify-center rounded-xl border border-dashed border-border bg-surface-soft px-3 sm:px-4 py-3 text-xs sm:text-sm text-muted-foreground transition-all duration-300 hover:border-primary/30 hover:text-foreground hover:bg-card cursor-default"
          >
            {name}
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}
