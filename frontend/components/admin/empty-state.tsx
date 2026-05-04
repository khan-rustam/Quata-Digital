import type { LucideIcon } from "lucide-react";
import { Inbox } from "lucide-react";
import { cn } from "@/lib/utils";

export function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  action,
  className,
}: {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-2xl border border-dashed border-border bg-surface-soft p-10 text-center",
        className
      )}
    >
      <div className="mx-auto inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-card border border-border text-muted-foreground">
        <Icon className="h-5 w-5" />
      </div>
      <div className="mt-4 text-base font-semibold tracking-tight">{title}</div>
      {description && (
        <p className="mt-1 text-sm text-muted-foreground max-w-md mx-auto">{description}</p>
      )}
      {action && <div className="mt-5 flex justify-center">{action}</div>}
    </div>
  );
}
