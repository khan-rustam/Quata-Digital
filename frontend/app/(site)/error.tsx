"use client";

import { useEffect } from "react";
import Link from "next/link";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * Segment-level error boundary for every public marketing page.
 *
 * Without this, an exception inside any `/`, `/about`, `/blog`, etc.
 * tree would bubble all the way up to the root error boundary, which
 * drops the navbar + footer. This one keeps the site chrome (provided
 * by the (site) layout) and only swaps the page body.
 */
export default function SiteSegmentError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[(site) error boundary]", error);
  }, [error]);

  return (
    <section className="container-page py-24">
      <div className="mx-auto max-w-xl text-center">
        <div className="mx-auto inline-flex h-12 w-12 items-center justify-center rounded-xl bg-rose-100 text-rose-700">
          <AlertTriangle className="h-5 w-5" />
        </div>
        <h1 className="mt-6 text-3xl md:text-4xl font-semibold tracking-tight text-balance">
          We couldn&apos;t render this page.
        </h1>
        <p className="mt-3 text-muted-foreground">
          Something went wrong on our end. The team has been notified.
          You can retry, or head back to the homepage.
        </p>
        {error?.digest && (
          <code className="mt-4 inline-block rounded-md bg-secondary px-3 py-1 text-xs font-mono">
            ref: {error.digest}
          </code>
        )}
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <Button onClick={reset}>
            <RefreshCw className="h-4 w-4" /> Try again
          </Button>
          <Button variant="outline" asChild>
            <Link href="/">Back home</Link>
          </Button>
        </div>
      </div>
    </section>
  );
}
