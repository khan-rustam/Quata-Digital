"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, Clock } from "lucide-react";
import { formatDate } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

export function FeaturedPost({
  post,
}: {
  post: {
    slug: string;
    title: string;
    excerpt: string;
    category: string;
    published_at: string;
    author?: string;
  };
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
    >
      <Link
        href={`/blog/${post.slug}`}
        className="group block rounded-3xl overflow-hidden border border-border bg-card ring-soft transition-all duration-300 hover:ring-elevated hover:-translate-y-1"
      >
        <div className="grid lg:grid-cols-2">
          <div className="relative aspect-16/10 lg:aspect-auto gradient-brand overflow-hidden">
            <div className="absolute inset-0 dot-grid opacity-20" />
            <div className="absolute inset-0 flex items-end p-6 sm:p-8 text-white/90">
              <Badge variant="outline" className="border-white/30 text-white">
                Featured
              </Badge>
            </div>
          </div>
          <div className="p-6 sm:p-8 md:p-10 flex flex-col justify-center">
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <Badge variant="brand">{post.category}</Badge>
              <span className="inline-flex items-center gap-1">
                <Clock className="h-3 w-3" /> {formatDate(post.published_at)}
              </span>
            </div>
            <h3 className="mt-4 text-xl sm:text-2xl md:text-3xl font-semibold tracking-tight">
              {post.title}
            </h3>
            <p className="mt-3 text-sm md:text-base text-muted-foreground">{post.excerpt}</p>
            <div className="mt-6 inline-flex items-center gap-1.5 text-sm font-medium text-primary">
              Read the full story
              <ArrowRight className="h-3.5 w-3.5 transition-transform duration-300 group-hover:translate-x-1" />
            </div>
          </div>
        </div>
      </Link>
    </motion.div>
  );
}
