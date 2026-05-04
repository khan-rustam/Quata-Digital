"use client";

import { Quote } from "lucide-react";
import { motion } from "framer-motion";

export type Testimonial = {
  quote: string;
  author: string;
  title: string;
  company: string;
  initials?: string;
};

const ease = [0.16, 1, 0.3, 1] as const;

export function Testimonials({ items }: { items: Testimonial[] }) {
  return (
    <motion.div
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, margin: "-60px" }}
      variants={{
        hidden: {},
        show: { transition: { staggerChildren: 0.08 } },
      }}
      className="grid gap-5 md:grid-cols-2 lg:grid-cols-3"
    >
      {items.map((t, i) => (
        <motion.figure
          key={i}
          variants={{
            hidden: { opacity: 0, y: 18 },
            show: { opacity: 1, y: 0, transition: { duration: 0.6, ease } },
          }}
          className="group relative flex h-full flex-col rounded-2xl border border-border bg-card p-6 ring-soft transition-all duration-300 hover:-translate-y-0.5 hover:ring-elevated"
        >
          <Quote className="h-6 w-6 text-primary opacity-60 transition-transform duration-300 group-hover:scale-110" />
          <blockquote className="mt-4 flex-1 text-[15px] leading-relaxed text-foreground/85">
            &ldquo;{t.quote}&rdquo;
          </blockquote>
          <figcaption className="mt-6 flex items-center gap-3 border-t border-border pt-4">
            <div className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-brand-soft text-primary text-xs font-semibold transition-colors duration-300 group-hover:bg-primary group-hover:text-white">
              {t.initials ?? t.author.split(" ").map((p) => p[0]).slice(0, 2).join("")}
            </div>
            <div className="min-w-0">
              <div className="text-sm font-semibold truncate">{t.author}</div>
              <div className="text-xs text-muted-foreground truncate">
                {t.title} · {t.company}
              </div>
            </div>
          </figcaption>
        </motion.figure>
      ))}
    </motion.div>
  );
}
