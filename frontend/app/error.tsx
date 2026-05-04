"use client";

import { useEffect } from "react";
import Link from "next/link";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Logo } from "@/components/site/logo";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Hook into Sentry / your monitoring here.
    console.error("[QUATA error boundary]", error);
  }, [error]);

  return (
    <div className="min-h-svh flex flex-col bg-background">
      <header className="container-page py-6">
        <Logo />
      </header>
      <main className="flex-1 container-page flex items-center justify-center py-20">
        <div className="max-w-xl text-center">
          <div className="mx-auto inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-rose-100 text-rose-700">
            <AlertTriangle className="h-6 w-6" />
          </div>
          <div className="mt-6 text-xs uppercase tracking-wider text-muted-foreground">
            Something went wrong
          </div>
          <h1 className="mt-3 text-4xl md:text-5xl font-semibold tracking-tight text-balance">
            That didn&apos;t work as expected.
          </h1>
          <p className="mt-4 text-muted-foreground">
            We&apos;ve logged the error — please try again, or head back to the
            homepage. If this keeps happening, contact us with the reference
            below.
          </p>
          {error?.digest && (
            <code className="mt-4 inline-block rounded-md bg-secondary px-3 py-1 text-xs font-mono">
              ref: {error.digest}
            </code>
          )}
          <div className="mt-8 flex flex-wrap justify-center gap-2">
            <Button onClick={reset}>
              <RefreshCw className="h-4 w-4" /> Try again
            </Button>
            <Button variant="outline" asChild>
              <Link href="/">Back home</Link>
            </Button>
            <Button variant="outline" asChild>
              <Link href="/contact">Contact us</Link>
            </Button>
          </div>
        </div>
      </main>
    </div>
  );
}
