import type { LucideIcon } from "lucide-react";
import { IconBadge } from "./icon-badge";
import { MotionList, MotionItem } from "./motion-list";
import { cn } from "@/lib/utils";

export type FeatureItem = {
  icon: LucideIcon;
  title: string;
  body: string;
  tone?: "brand" | "amber" | "rose" | "sky" | "violet" | "emerald" | "ink" | "neutral";
};

export function FeatureGrid({
  items,
  columns = 3,
  variant = "card",
  className,
}: {
  items: FeatureItem[];
  columns?: 2 | 3 | 4;
  variant?: "card" | "minimal" | "bordered";
  className?: string;
}) {
  const gridCols = {
    2: "sm:grid-cols-2",
    3: "sm:grid-cols-2 lg:grid-cols-3",
    4: "sm:grid-cols-2 lg:grid-cols-4",
  }[columns];

  return (
    <MotionList className={cn("grid gap-5", gridCols, className)}>
      {items.map((item, i) => (
        <MotionItem key={i}>
          <FeatureCard item={item} variant={variant} />
        </MotionItem>
      ))}
    </MotionList>
  );
}

function FeatureCard({ item, variant }: { item: FeatureItem; variant: "card" | "minimal" | "bordered" }) {
  if (variant === "minimal") {
    return (
      <div className="flex gap-4 group">
        <span className="transition-transform duration-300 group-hover:-rotate-6 group-hover:scale-110">
          <IconBadge icon={item.icon} tone={item.tone ?? "brand"} size="md" />
        </span>
        <div>
          <div className="text-base font-semibold tracking-tight">{item.title}</div>
          <p className="mt-1.5 text-sm text-muted-foreground">{item.body}</p>
        </div>
      </div>
    );
  }
  if (variant === "bordered") {
    return (
      <div className="group h-full rounded-2xl border border-border p-6 transition-all duration-300 hover:border-primary/30 hover:bg-surface-soft hover:-translate-y-0.5">
        <span className="inline-block transition-transform duration-300 group-hover:-rotate-6 group-hover:scale-110">
          <IconBadge icon={item.icon} tone={item.tone ?? "brand"} />
        </span>
        <div className="mt-5 text-base font-semibold tracking-tight">{item.title}</div>
        <p className="mt-2 text-sm text-muted-foreground">{item.body}</p>
      </div>
    );
  }
  return (
    <div className="group h-full rounded-2xl border border-border bg-card p-6 ring-soft transition-all duration-300 hover:-translate-y-1 hover:ring-elevated">
      <span className="inline-block transition-transform duration-300 group-hover:-rotate-6 group-hover:scale-110">
        <IconBadge icon={item.icon} tone={item.tone ?? "brand"} />
      </span>
      <div className="mt-5 text-base font-semibold tracking-tight">{item.title}</div>
      <p className="mt-2 text-sm text-muted-foreground">{item.body}</p>
    </div>
  );
}
