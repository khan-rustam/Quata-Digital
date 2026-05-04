import { Sparkles } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { MotionList, MotionItem } from "./motion-list";

export type TimelineEntry = {
  date: string;
  title: string;
  body: string;
  icon?: LucideIcon;
};

export function Timeline({ entries }: { entries: TimelineEntry[] }) {
  return (
    <MotionList className="relative" staggerChildren={0.1}>
      <span className="absolute left-[15px] top-3 bottom-3 w-px bg-linear-to-b from-primary via-border to-transparent" aria-hidden />
      {entries.map((entry, i) => {
        const Icon = entry.icon ?? Sparkles;
        return (
          <MotionItem key={i} y={12}>
            <div className="group relative pl-12 pb-10 last:pb-0">
              <span className="absolute left-0 top-1 inline-flex h-8 w-8 items-center justify-center rounded-full bg-card border border-border ring-4 ring-background transition-all duration-300 group-hover:bg-primary group-hover:border-primary group-hover:scale-110">
                <Icon className="h-4 w-4 text-primary transition-colors duration-300 group-hover:text-white" />
              </span>
              <div className="text-xs uppercase tracking-wider text-muted-foreground">
                {entry.date}
              </div>
              <div className="mt-1 text-base font-semibold tracking-tight">{entry.title}</div>
              <p className="mt-1.5 text-sm text-muted-foreground max-w-2xl">{entry.body}</p>
            </div>
          </MotionItem>
        );
      })}
    </MotionList>
  );
}
