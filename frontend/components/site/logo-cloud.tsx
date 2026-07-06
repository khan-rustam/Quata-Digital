"use client";

import { motion } from "framer-motion";

// Real, permissioned partner names go here as they are confirmed. Left empty
// on purpose (boss Q6): the previous entries ("Aerial Bank", "Sahel Telco",
// …) were invented placeholders and stating them as real partners is a
// reputational/legal risk. While this list is empty, neutral "coming soon"
// slots render instead of fake company names — drop real names in to go live.
const partners: string[] = [];

const PLACEHOLDER_SLOTS = 6;

const ease = [0.16, 1, 0.3, 1] as const;

export function LogoCloud() {
  const hasPartners = partners.length > 0;
  const tiles = hasPartners
    ? partners
    : Array.from({ length: PLACEHOLDER_SLOTS }, (_, i) => `slot-${i}`);

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
        {hasPartners
          ? "Trusted by partners building across the continent"
          : "Partnerships announced soon"}
      </div>
      <div className="mt-6 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3 sm:gap-4 items-center">
        {tiles.map((name) => (
          <motion.div
            key={name}
            variants={{
              hidden: { opacity: 0, y: 8 },
              show: { opacity: 1, y: 0, transition: { duration: 0.4, ease } },
            }}
            className="flex items-center justify-center rounded-xl border border-dashed border-border bg-surface-soft px-3 sm:px-4 py-3 text-xs sm:text-sm text-muted-foreground transition-all duration-300 hover:border-primary/30 hover:text-foreground hover:bg-card cursor-default"
          >
            {hasPartners ? name : "Coming soon"}
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}
