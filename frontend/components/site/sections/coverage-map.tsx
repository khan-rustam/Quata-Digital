"use client";

import { CheckCircle2, Clock, MapPin } from "lucide-react";
import { motion } from "framer-motion";

// Real coverage as of May 2026 launch.
const live = ["Cameroon"];
const expanding: string[] = [];
const planned = [
  "Nigeria",
  "Ghana",
  "Senegal",
  "Côte d'Ivoire",
  "Kenya",
  "Tanzania",
  "Uganda",
  "Rwanda",
  "South Africa",
  "Egypt",
  "Morocco",
  "Ethiopia",
];

const ease = [0.16, 1, 0.3, 1] as const;

function Group({
  title,
  countries,
  emptyText,
  icon: Icon,
  iconClass,
  borderClass,
  bgClass,
  index,
}: {
  title: string;
  countries: string[];
  emptyText?: string;
  icon: typeof CheckCircle2;
  iconClass: string;
  borderClass: string;
  bgClass: string;
  index: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.55, delay: index * 0.08, ease }}
      className={`group rounded-2xl border ${borderClass} ${bgClass} p-5 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md`}
    >
      <div className="flex items-center gap-2">
        <Icon className={`h-4 w-4 ${iconClass} transition-transform duration-300 group-hover:scale-110`} />
        <div className="text-sm font-semibold">{title}</div>
        <div className="text-xs text-muted-foreground ml-auto">
          {countries.length} {countries.length === 1 ? "market" : "markets"}
        </div>
      </div>
      {countries.length === 0 ? (
        <div className="mt-4 text-xs text-muted-foreground italic">
          {emptyText ?? "Nothing yet."}
        </div>
      ) : (
        <div className="mt-4 flex flex-wrap gap-1.5">
          {countries.map((c) => (
            <span
              key={c}
              className="inline-flex items-center gap-1 rounded-full bg-surface border border-border px-2.5 py-1 text-xs transition-colors duration-200 hover:border-primary/40 hover:text-primary"
            >
              <MapPin className="h-3 w-3 text-muted-foreground" />
              {c}
            </span>
          ))}
        </div>
      )}
    </motion.div>
  );
}

export function CoverageMap() {
  return (
    <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <Group
        title="Live"
        countries={live}
        icon={CheckCircle2}
        iconClass="text-emerald-700"
        borderClass="border-emerald-200"
        bgClass="bg-emerald-50/40"
        index={0}
      />
      <Group
        title="Expanding"
        countries={expanding}
        emptyText="Next markets announced as we launch them."
        icon={Clock}
        iconClass="text-amber-700"
        borderClass="border-amber-200"
        bgClass="bg-amber-50/40"
        index={1}
      />
      <Group
        title="Planned"
        countries={planned}
        icon={MapPin}
        iconClass="text-sky-700"
        borderClass="border-sky-200"
        bgClass="bg-sky-50/40"
        index={2}
      />
    </div>
  );
}
