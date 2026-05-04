import Link from "next/link";
import { ArrowLeft, Compass } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function AdminNotFound() {
  return (
    <div className="flex-1 min-w-0 flex items-center justify-center min-h-svh">
      <div className="max-w-md text-center px-6">
        <div className="mx-auto inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-soft text-primary">
          <Compass className="h-5 w-5" />
        </div>
        <div className="mt-5 text-xs uppercase tracking-wider text-muted-foreground">
          404 — Admin
        </div>
        <h1 className="mt-2 text-2xl md:text-3xl font-semibold tracking-tight">
          That admin page doesn&apos;t exist.
        </h1>
        <p className="mt-3 text-sm text-muted-foreground">
          The page may have moved, or you may not have access to it.
        </p>
        <Button asChild className="mt-6">
          <Link href="/admin/overview">
            <ArrowLeft className="h-4 w-4" /> Back to overview
          </Link>
        </Button>
      </div>
    </div>
  );
}
