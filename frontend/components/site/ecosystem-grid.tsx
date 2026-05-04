"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowUpRight } from "lucide-react";
import { products } from "@/lib/ecosystem";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const statusVariant = {
  Live: "live",
  Beta: "beta",
  "Coming Soon": "soon",
  Planned: "outline",
} as const;

const ease = [0.16, 1, 0.3, 1] as const;

export function EcosystemGrid() {
  return (
    <motion.div
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, margin: "-60px" }}
      variants={{
        hidden: {},
        show: { transition: { staggerChildren: 0.06, delayChildren: 0.05 } },
      }}
      className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-5"
    >
      {products.map((p) => (
        <motion.div
          key={p.slug}
          variants={{
            hidden: { opacity: 0, y: 18 },
            show: { opacity: 1, y: 0, transition: { duration: 0.55, ease } },
          }}
        >
          <Link
            href={`/ecosystem/${p.slug}`}
            className="group relative flex h-full flex-col overflow-hidden rounded-2xl border border-border bg-card ring-soft transition-all duration-300 hover:-translate-y-1 hover:ring-elevated"
          >
            <div
              className={cn(
                "h-28 w-full bg-linear-to-br relative overflow-hidden",
                p.accent
              )}
            >
              <div className="absolute inset-0 mix-blend-overlay opacity-40 dot-grid transition-opacity duration-500 group-hover:opacity-60" />
              <div className="absolute right-4 top-4 inline-flex items-center gap-1.5 rounded-full bg-white/90 px-2.5 py-1 text-[11px] font-medium text-ink">
                {p.category}
              </div>
              <div className="absolute left-5 bottom-4 text-white text-2xl font-semibold tracking-tight drop-shadow-sm transition-transform duration-300 group-hover:translate-x-1">
                {p.name}
              </div>
            </div>
            <div className="flex flex-1 flex-col gap-3 p-5">
              <div className="flex items-center justify-between">
                <Badge variant={statusVariant[p.status]}>
                  <span className="inline-block h-1.5 w-1.5 rounded-full bg-current opacity-70" />
                  {p.status}
                </Badge>
                <ArrowUpRight className="h-4 w-4 text-muted-foreground transition-all duration-300 group-hover:text-primary group-hover:-translate-y-1 group-hover:translate-x-1" />
              </div>
              <div className="text-base font-medium tracking-tight">
                {p.tagline}
              </div>
              <p className="text-sm text-muted-foreground line-clamp-3">{p.description}</p>
            </div>
          </Link>
        </motion.div>
      ))}
    </motion.div>
  );
}
