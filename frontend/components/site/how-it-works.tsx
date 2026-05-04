"use client";

import { motion } from "framer-motion";
import {
  Wallet,
  Layers3,
  ShoppingBag,
  HeartPulse,
  Building2,
  Utensils,
  Store,
} from "lucide-react";

// Real 3-layer model:
//   1. Payments rail        → QUATAPAY
//   2. Business operations  → ABAQWA  (NOT mobility — confirmed by leadership)
//   3. Commerce surfaces    → QUATAFOOD, 88BASKET, 88BRICKZ, O3MALL, QMEDIQ
const layers = [
  {
    title: "Payments rail",
    body: "QUATAPAY moves money — Mobile Money, cards, payment links and QR.",
    icon: Wallet,
    accent: "from-emerald-700 to-emerald-500",
  },
  {
    title: "Business operations",
    body: "ABAQWA helps businesses manage operations, sales and analytics from one system.",
    icon: Layers3,
    accent: "from-amber-500 to-amber-300",
  },
  {
    title: "Commerce surfaces",
    body: "QUATAFOOD, 88BASKET, O3MALL, 88BRICKZ and QMEDIQ deliver the experiences.",
    icon: ShoppingBag,
    accent: "from-sky-600 to-cyan-400",
  },
];

const surfaces = [
  { icon: Utensils, name: "Quatafood" },
  { icon: ShoppingBag, name: "88Basket" },
  { icon: Store, name: "O3Mall" },
  { icon: Building2, name: "88Brickz" },
  { icon: HeartPulse, name: "QMediq" },
];

export function HowItWorks() {
  return (
    <div className="relative">
      <motion.div
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, margin: "-60px" }}
        variants={{
          hidden: {},
          show: { transition: { staggerChildren: 0.1 } },
        }}
        className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5"
      >
        {layers.map((l, i) => (
          <motion.div
            key={l.title}
            variants={{
              hidden: { opacity: 0, y: 18 },
              show: { opacity: 1, y: 0, transition: { duration: 0.55, ease: [0.16, 1, 0.3, 1] } },
            }}
            className="group relative rounded-2xl border border-border bg-card p-6 ring-soft transition-all duration-300 hover:-translate-y-1 hover:ring-elevated"
          >
            <div
              className={`inline-flex h-10 w-10 items-center justify-center rounded-xl text-white bg-linear-to-br transition-transform duration-300 group-hover:scale-110 group-hover:-rotate-6 ${l.accent}`}
            >
              <l.icon className="h-5 w-5" />
            </div>
            <div className="mt-4 text-lg font-semibold tracking-tight">
              {l.title}
            </div>
            <p className="mt-2 text-sm text-muted-foreground">{l.body}</p>
            <div className="mt-6 flex items-center gap-2 text-xs text-muted-foreground">
              <span className="inline-block h-1 w-1 rounded-full bg-primary" />
              Layer {i + 1}
            </div>
          </motion.div>
        ))}
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 14 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-60px" }}
        transition={{ duration: 0.55, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
        className="mt-10 rounded-2xl border border-border bg-surface-soft p-6 md:p-8"
      >
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
          <div className="flex items-center gap-4">
            <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl gradient-brand text-white">
              <Wallet className="h-5 w-5" />
            </div>
            <div>
              <div className="text-sm font-medium">QUATAPAY wallet</div>
              <div className="text-xs text-muted-foreground">
                The single balance behind every product on the rail.
              </div>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {surfaces.map((s) => (
              <div
                key={s.name}
                className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1.5 text-xs transition-colors duration-200 hover:border-primary/40 hover:text-primary cursor-default"
              >
                <s.icon className="h-3.5 w-3.5 text-primary" />
                {s.name}
              </div>
            ))}
          </div>
        </div>
      </motion.div>
    </div>
  );
}
