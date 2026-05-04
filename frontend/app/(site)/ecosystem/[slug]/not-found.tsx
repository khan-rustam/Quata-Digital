import Link from "next/link";
import { ArrowRight, Sparkles } from "lucide-react";
import { Section } from "@/components/site/section";
import { Button } from "@/components/ui/button";
import { products } from "@/lib/ecosystem";

export default function ProductNotFound() {
  return (
    <Section className="max-w-3xl mx-auto py-20 text-center">
      <div className="mx-auto inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-soft text-primary">
        <Sparkles className="h-5 w-5" />
      </div>
      <div className="mt-6 text-xs uppercase tracking-wider text-muted-foreground">
        Product not found
      </div>
      <h1 className="mt-3 text-3xl md:text-5xl font-semibold tracking-tight text-balance">
        We don&rsquo;t have a product at that URL — yet.
      </h1>
      <p className="mt-4 text-muted-foreground">
        Check the spelling or pick one of the live ones below.
      </p>

      <div className="mt-10 grid gap-3 sm:grid-cols-2 text-left">
        {products.map((p) => (
          <Link
            key={p.slug}
            href={`/ecosystem/${p.slug}`}
            className="group rounded-2xl border border-border bg-card p-4 ring-soft transition hover:-translate-y-0.5"
          >
            <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
              {p.category}
            </div>
            <div className="mt-1 flex items-center justify-between gap-3">
              <div className="text-sm font-semibold tracking-tight">
                {p.name}
              </div>
              <ArrowRight className="h-3.5 w-3.5 text-muted-foreground transition group-hover:translate-x-0.5 group-hover:text-foreground" />
            </div>
            <p className="mt-2 text-xs text-muted-foreground line-clamp-2">
              {p.tagline}
            </p>
          </Link>
        ))}
      </div>

      <div className="mt-10">
        <Button variant="outline" asChild>
          <Link href="/ecosystem">Back to the ecosystem</Link>
        </Button>
      </div>
    </Section>
  );
}
