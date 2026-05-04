import type { LucideIcon } from "lucide-react";
import { ArrowRight } from "lucide-react";
import { IconBadge } from "./icon-badge";
import { MotionList, MotionItem } from "./motion-list";

export type ProcessStep = {
  icon: LucideIcon;
  title: string;
  body: string;
  duration?: string;
};

export function ProcessSteps({
  steps,
  layout = "horizontal",
}: {
  steps: ProcessStep[];
  layout?: "horizontal" | "vertical";
}) {
  if (layout === "vertical") {
    return (
      <MotionList className="relative" staggerChildren={0.08}>
        <span className="absolute left-[19px] top-2 bottom-2 w-px bg-border" aria-hidden />
        {steps.map((step, i) => (
          <MotionItem key={i} y={12}>
            <div className="group relative pl-14 pb-8 last:pb-0">
              <span className="absolute left-0 top-0 inline-flex h-10 w-10 items-center justify-center rounded-full bg-brand-soft text-primary text-sm font-bold ring-4 ring-background transition-all duration-300 group-hover:bg-primary group-hover:text-white group-hover:scale-105">
                {i + 1}
              </span>
              <div className="flex items-center gap-3">
                <step.icon className="h-4 w-4 text-primary" />
                <div className="text-base font-semibold tracking-tight">{step.title}</div>
                {step.duration && (
                  <span className="text-xs text-muted-foreground">{step.duration}</span>
                )}
              </div>
              <p className="mt-2 text-sm text-muted-foreground">{step.body}</p>
            </div>
          </MotionItem>
        ))}
      </MotionList>
    );
  }

  return (
    <MotionList className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" staggerChildren={0.08}>
      {steps.map((step, i) => (
        <MotionItem key={i}>
          <div className="group h-full relative rounded-2xl border border-border bg-card p-6 ring-soft transition-all duration-300 hover:-translate-y-0.5 hover:ring-elevated">
            <div className="flex items-center justify-between">
              <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-brand-soft text-primary text-xs font-bold transition-colors duration-300 group-hover:bg-primary group-hover:text-white">
                {String(i + 1).padStart(2, "0")}
              </span>
              <span className="inline-block transition-transform duration-300 group-hover:-rotate-6 group-hover:scale-110">
                <IconBadge icon={step.icon} tone="neutral" size="sm" />
              </span>
            </div>
            <div className="mt-5 text-base font-semibold tracking-tight">{step.title}</div>
            <p className="mt-2 text-sm text-muted-foreground">{step.body}</p>
            {step.duration && (
              <div className="mt-4 inline-flex items-center gap-1.5 text-[11px] text-muted-foreground border-t border-dashed border-border pt-3">
                <ArrowRight className="h-3 w-3 text-primary" />
                {step.duration}
              </div>
            )}
          </div>
        </MotionItem>
      ))}
    </MotionList>
  );
}
