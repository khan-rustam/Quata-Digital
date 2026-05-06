import { Loader2 } from "lucide-react";

/** Admin route loader — minimal, since the admin shell stays in place during
 *  client navigation. Mainly visible on hard refresh / first paint. */
export default function AdminLoading() {
  return (
    <div
      className="flex h-svh w-full items-center justify-center"
      role="status"
      aria-label="Loading"
    >
      <div className="flex flex-col items-center gap-3 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" />
        <span className="text-xs uppercase tracking-wider">Loading…</span>
      </div>
    </div>
  );
}
