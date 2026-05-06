import { Logo } from "@/components/site/logo";

/**
 * Public-site route loader. Shown while a Server Component is fetching its
 * data on a hard navigation (or refresh). Kept minimal — a thin progress
 * shimmer at the top + branded centerpiece — so it never feels like the site
 * has frozen.
 */
export default function SiteLoading() {
  return (
    <div className="min-h-svh flex flex-col bg-background" role="status" aria-label="Loading">
      <div
        aria-hidden
        className="h-0.5 w-full overflow-hidden bg-brand-soft"
      >
        <div
          className="h-full w-1/3 -translate-x-full animate-[loading-stripe_1.1s_linear_infinite]"
          style={{
            background:
              "linear-gradient(90deg, transparent, rgb(14 91 74) 50%, transparent)",
          }}
        />
      </div>
      <header className="container-page py-6">
        <Logo />
      </header>
      <main className="flex-1 container-page py-16">
        <div className="max-w-4xl mx-auto grid gap-6">
          <div className="h-10 w-3/4 rounded-lg bg-secondary/60 animate-pulse" />
          <div className="h-4 w-2/3 rounded-md bg-secondary/50 animate-pulse" />
          <div className="h-4 w-1/2 rounded-md bg-secondary/40 animate-pulse" />
          <div className="mt-6 grid gap-4 sm:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                className="h-40 rounded-2xl border border-border bg-card/60 animate-pulse"
              />
            ))}
          </div>
        </div>
      </main>
      <span className="sr-only">Loading…</span>
      <style>{`
        @keyframes loading-stripe {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(400%); }
        }
      `}</style>
    </div>
  );
}
