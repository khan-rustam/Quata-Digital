"use client";

/**
 * Tiny client-side stagger wrappers used by server-rendered grids.
 *
 * Why split? Server pages pass Lucide icons (function refs) as props to grids.
 * Function refs can't cross the server→client boundary, so the grid itself
 * must stay a server component and only delegate motion to these wrappers.
 */

import * as React from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

const ease = [0.16, 1, 0.3, 1] as const;

export function MotionList({
  children,
  className,
  staggerChildren = 0.06,
  delayChildren = 0.05,
}: {
  children: React.ReactNode;
  className?: string;
  staggerChildren?: number;
  delayChildren?: number;
}) {
  return (
    <motion.div
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, margin: "-60px" }}
      variants={{
        hidden: {},
        show: { transition: { staggerChildren, delayChildren } },
      }}
      className={cn(className)}
    >
      {children}
    </motion.div>
  );
}

export function MotionItem({
  children,
  className,
  y = 16,
  duration = 0.5,
}: {
  children: React.ReactNode;
  className?: string;
  y?: number;
  duration?: number;
}) {
  return (
    <motion.div
      variants={{
        hidden: { opacity: 0, y },
        show: { opacity: 1, y: 0, transition: { duration, ease } },
      }}
      className={cn("h-full", className)}
    >
      {children}
    </motion.div>
  );
}
