"use client";

import Image from "next/image";
import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowUpRight } from "lucide-react";
import { products } from "@/lib/ecosystem";
import { Badge } from "@/components/ui/badge";

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
            className="group relative flex h-full flex-col rounded-2xl border border-border bg-card ring-soft transition-all duration-300 hover:-translate-y-1 hover:ring-elevated hover:border-primary/30 overflow-hidden"
          >
            {/* Top row — category + arrow */}
            <div className="flex items-center justify-between px-6 pt-5">
              <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                {p.category}
              </span>
              <ArrowUpRight className="h-4 w-4 text-muted-foreground transition-all duration-300 group-hover:text-primary group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
            </div>

            {/* Logo plate — big, centered, on a soft tinted panel */}
            <div className="mx-6 mt-4 rounded-xl bg-surface-soft border border-border/60 h-32 flex items-center justify-center px-6">
              <Image
                src={p.logo}
                alt={`${p.name} logo`}
                width={400}
                height={300}
                className="max-h-24 w-auto object-contain transition-transform duration-300 group-hover:scale-105"
              />
            </div>

            {/* Status + tagline + description */}
            <div className="flex flex-1 flex-col px-6 pt-5 pb-5">
              <Badge variant={statusVariant[p.status]} className="self-start">
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-current opacity-70" />
                {p.status}
              </Badge>

              <div className="mt-3 text-base font-semibold tracking-tight text-foreground">
                {p.tagline}
              </div>
              <p className="mt-2 text-sm text-muted-foreground line-clamp-2 flex-1">
                {p.shortDescription}
              </p>

              <div className="mt-5 pt-4 border-t border-border flex items-center justify-between text-xs">
                <span className="text-muted-foreground">
                  {p.launch ?? "Roadmap"}
                </span>
                <span className="font-medium text-primary inline-flex items-center gap-1">
                  Learn more
                  <ArrowUpRight className="h-3 w-3 transition group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                </span>
              </div>
            </div>
          </Link>
        </motion.div>
      ))}
    </motion.div>
  );
}
