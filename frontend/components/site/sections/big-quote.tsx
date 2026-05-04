"use client";

import { Quote } from "lucide-react";
import { motion } from "framer-motion";

export function BigQuote({
  quote,
  author,
  role,
}: {
  quote: string;
  author: string;
  role?: string;
}) {
  return (
    <motion.figure
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      className="relative overflow-hidden rounded-3xl border border-border bg-surface-soft p-8 sm:p-10 md:p-14"
    >
      <Quote className="absolute -top-2 -left-2 h-32 w-32 text-primary/5" />
      <blockquote className="relative text-xl sm:text-2xl md:text-3xl font-medium tracking-tight leading-snug max-w-3xl">
        &ldquo;{quote}&rdquo;
      </blockquote>
      <figcaption className="relative mt-6 text-sm">
        <span className="font-semibold">— {author}</span>
        {role && <span className="text-muted-foreground"> · {role}</span>}
      </figcaption>
    </motion.figure>
  );
}
