"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, Sparkles, Wallet, MapPin, Rocket } from "lucide-react";
import { Button } from "@/components/ui/button";
import { StatStrip } from "@/components/site/sections/stat-strip";

export function Hero() {
  return (
    <section className="relative overflow-hidden -mt-20">
      <div className="absolute inset-0 -z-10 bg-linear-to-b from-brand-soft/40 via-surface to-surface" />
      <div className="absolute inset-0 -z-10 dot-grid mask-fade-b opacity-60" />
      <div
        className="absolute -top-40 -right-32 -z-10 h-[480px] w-[480px] rounded-full opacity-30 blur-3xl"
        style={{
          background:
            "radial-gradient(closest-side, rgba(232,177,74,0.55), transparent)",
        }}
      />
      <div
        className="absolute -bottom-40 -left-32 -z-10 h-[520px] w-[520px] rounded-full opacity-40 blur-3xl"
        style={{
          background:
            "radial-gradient(closest-side, rgba(14,91,74,0.45), transparent)",
        }}
      />

      <div className="container-page pt-32 sm:pt-36 md:pt-44 pb-16 sm:pb-20 md:pb-28">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="inline-flex items-center gap-2 rounded-full border border-border bg-surface/80 px-3 py-1 text-xs text-muted-foreground backdrop-blur"
        >
          <Sparkles className="h-3.5 w-3.5 text-primary" />
          <span className="hidden xs:inline">Founded 2025 in Cameroon · 7 products · Built for Africa</span>
          <span className="xs:hidden">2025 · Cameroon · 7 products</span>
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.05 }}
          className="mt-5 sm:mt-6 text-[2.25rem] leading-[1.05] sm:text-5xl md:text-7xl font-semibold tracking-tight text-balance md:leading-[1.02]"
        >
          Africa&apos;s connected{" "}
          <span className="text-gradient-brand">digital ecosystem.</span>{" "}
          <br className="hidden md:block" />
          One rail. Seven products.
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="mt-5 sm:mt-6 max-w-2xl text-base sm:text-lg text-muted-foreground"
        >
          QUATA Digital unifies payments, business operations and commerce on a
          single rail — so people, businesses and partners can move money,
          goods and services across the continent without friction.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.15 }}
          className="mt-7 sm:mt-9 flex flex-wrap items-center gap-3"
        >
          <Button size="lg" asChild className="w-full sm:w-auto">
            <Link href="/ecosystem">
              Explore the ecosystem <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
          <Button size="lg" variant="outline" asChild className="w-full sm:w-auto">
            <Link href="/partners">Become a partner</Link>
          </Button>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="mt-12 sm:mt-16"
        >
          <StatStrip
            variant="card"
            items={[
              { value: "7", label: "Products in the ecosystem", icon: Sparkles, tone: "brand" },
              { value: "1", label: "Unified wallet", icon: Wallet, tone: "amber" },
              { value: "May 2026", label: "First products live", icon: Rocket, tone: "sky" },
              { value: "Bamenda, CM", label: "Headquarters", icon: MapPin, tone: "violet" },
            ]}
          />
        </motion.div>
      </div>
    </section>
  );
}
