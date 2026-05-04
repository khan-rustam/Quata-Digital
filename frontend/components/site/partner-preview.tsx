"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, Briefcase, Building2, Coins, Users } from "lucide-react";

const paths = [
  {
    slug: "business",
    title: "Business partner",
    body: "Join the ecosystem as a merchant. Accept payments and use QUATA services.",
    icon: Building2,
    tone: "from-emerald-500 to-emerald-700",
  },
  {
    slug: "strategic",
    title: "Strategic partner",
    body: "Banks, telcos and logistics — integrate via APIs.",
    icon: Briefcase,
    tone: "from-sky-500 to-sky-700",
  },
  {
    slug: "investor",
    title: "Investor / Capital",
    body: "Request the pitch deck and submit interest.",
    icon: Coins,
    tone: "from-amber-500 to-amber-700",
  },
  {
    slug: "service",
    title: "Service partner",
    body: "Riders, drivers, vendors and field agents.",
    icon: Users,
    tone: "from-rose-500 to-rose-700",
  },
];

const ease = [0.16, 1, 0.3, 1] as const;

export function PartnerPreview() {
  return (
    <motion.div
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, margin: "-60px" }}
      variants={{
        hidden: {},
        show: { transition: { staggerChildren: 0.07 } },
      }}
      className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5"
    >
      {paths.map((p) => (
        <motion.div
          key={p.slug}
          variants={{
            hidden: { opacity: 0, y: 18 },
            show: { opacity: 1, y: 0, transition: { duration: 0.55, ease } },
          }}
        >
          <Link
            href={`/partners/${p.slug}`}
            className="group relative flex h-full flex-col overflow-hidden rounded-2xl border border-border bg-card p-6 ring-soft transition-all duration-300 hover:-translate-y-1 hover:ring-elevated"
          >
            {/* Soft accent glow */}
            <span
              aria-hidden
              className={`absolute -top-12 -right-12 h-32 w-32 rounded-full opacity-0 blur-2xl transition-opacity duration-500 group-hover:opacity-40 bg-linear-to-br ${p.tone}`}
            />
            <div className={`relative inline-flex h-10 w-10 items-center justify-center rounded-xl bg-brand-soft text-primary transition-all duration-300 group-hover:bg-linear-to-br group-hover:text-white group-hover:scale-110 group-hover:-rotate-6 ${p.tone}`}>
              <p.icon className="h-5 w-5" />
            </div>
            <div className="relative mt-5 text-base font-semibold tracking-tight">
              {p.title}
            </div>
            <p className="relative mt-2 text-sm text-muted-foreground flex-1">{p.body}</p>
            <div className="relative mt-5 inline-flex items-center gap-1.5 text-sm font-medium text-primary">
              Apply <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-1" />
            </div>
          </Link>
        </motion.div>
      ))}
    </motion.div>
  );
}
