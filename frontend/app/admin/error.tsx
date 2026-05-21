"use client";

import { useEffect } from "react";
import Link from "next/link";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * Segment-level error boundary for the entire admin shell.
 *
 * Without this an exception inside any `/admin/*` page bubbles to the
 * root boundary, dropping the admin sidebar and looking like a full
 * outage to the operator. This boundary keeps the admin chrome and
 * scopes the error message to the failing page.
 */
export default function AdminSegmentError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[admin error boundary]", error);
  }, [error]);

  return (
    <div className="p-6">
      <div className="rounded-2xl border border-border bg-card p-8 text-center">
        <div className="mx-auto inline-flex h-12 w-12 items-center justify-center rounded-xl bg-rose-100 text-rose-700">
          <AlertTriangle className="h-5 w-5" />
        </div>
        <h1 className="mt-5 text-2xl font-semibold tracking-tight">
          This admin page failed to render.
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          The exception has been logged. Try again, or jump to another
          section from the sidebar.
        </p>
        {error?.digest && (
          <code className="mt-3 inline-block rounded-md bg-secondary px-3 py-1 text-xs font-mono">
            ref: {error.digest}
          </code>
        )}
        <div className="mt-5 flex flex-wrap justify-center gap-2">
          <Button onClick={reset}>
            <RefreshCw className="h-4 w-4" /> Retry
          </Button>
          <Button variant="outline" asChild>
            <Link href="/admin/overview">Overview</Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
