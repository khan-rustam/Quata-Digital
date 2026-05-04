import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";

export function FinalCTA() {
  return (
    <div className="relative overflow-hidden rounded-3xl border border-border bg-ink text-white">
      <div className="absolute inset-0 opacity-25 dot-grid" />
      <div
        className="absolute -top-32 -left-32 h-96 w-96 rounded-full opacity-40 blur-3xl"
        style={{
          background:
            "radial-gradient(closest-side, rgba(52,211,167,0.55), transparent)",
        }}
      />
      <div
        className="absolute -bottom-32 -right-20 h-96 w-96 rounded-full opacity-40 blur-3xl"
        style={{
          background:
            "radial-gradient(closest-side, rgba(232,177,74,0.55), transparent)",
        }}
      />
      <div className="relative px-6 py-14 md:px-14 md:py-20 grid md:grid-cols-2 gap-8 items-center">
        <div>
          <h3 className="text-3xl md:text-5xl font-semibold tracking-tight text-balance">
            Build with the rail powering Africa&apos;s daily life.
          </h3>
          <p className="mt-4 text-white/70 max-w-xl">
            Whether you&apos;re a merchant, a rider, a bank or a builder — there is a
            way to plug into QUATA. Start with a single conversation.
          </p>
        </div>
        <div className="flex flex-wrap gap-3 md:justify-end">
          <Button size="xl" variant="accent" asChild>
            <Link href="/partners">
              Become a partner <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
          <Button
            size="xl"
            variant="outline"
            asChild
            className="bg-white/0 text-white border-white/20 hover:bg-white/10 hover:text-white"
          >
            <Link href="/contact">Talk to sales</Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
