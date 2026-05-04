"use client";

import { motion } from "framer-motion";

const logos = [
  "Aerial Bank",
  "Sahel Telco",
  "Pulse Logistics",
  "Mara Foods",
  "Karoo Retail",
  "Niger River Group",
];

const ease = [0.16, 1, 0.3, 1] as const;

export function LogoCloud() {
  return (
    <motion.div
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, margin: "-60px" }}
      variants={{
        hidden: {},
        show: { transition: { staggerChildren: 0.04, delayChildren: 0.05 } },
      }}
      className="container-page py-10"
    >
      <div className="text-center text-xs uppercase tracking-wider text-muted-foreground">
        Trusted by partners building across the continent
      </div>
      <div className="mt-6 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3 sm:gap-4 items-center">
        {logos.map((name) => (
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
