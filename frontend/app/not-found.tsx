import Link from "next/link";
import { ArrowLeft, Compass, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Logo } from "@/components/site/logo";

export default function NotFound() {
  return (
    <div className="min-h-svh flex flex-col bg-background">
      <header className="container-page py-6">
        <Logo />
      </header>
      <main className="flex-1 container-page flex items-center justify-center py-20">
        <div className="max-w-xl text-center">
          <div className="mx-auto inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-soft text-primary">
            <Compass className="h-6 w-6" />
          </div>
          <div className="mt-6 text-xs uppercase tracking-wider text-muted-foreground">
            Error 404
          </div>
          <h1 className="mt-3 text-4xl md:text-5xl font-semibold tracking-tight text-balance">
            We can&apos;t find that page.
          </h1>
          <p className="mt-4 text-muted-foreground">
            The page you were looking for has moved, was renamed, or never
            existed. Try one of the routes below — or head back to the homepage.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-2">
            <Button asChild>
              <Link href="/">
                <ArrowLeft className="h-4 w-4" /> Back home
              </Link>
            </Button>
            <Button variant="outline" asChild>
              <Link href="/ecosystem">Explore the ecosystem</Link>
            </Button>
            <Button variant="outline" asChild>
              <Link href="/contact">Contact us</Link>
            </Button>
          </div>

          <div className="mt-12 grid sm:grid-cols-3 gap-3 text-left">
            {[
              { href: "/partners", label: "Partner gateway" },
              { href: "/careers", label: "Open roles" },
              { href: "/blog", label: "News & insights" },
            ].map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="rounded-2xl border border-border bg-card p-5 ring-soft hover:ring-elevated transition flex items-center justify-between"
              >
                <span className="text-sm font-medium">{link.label}</span>
                <Search className="h-4 w-4 text-muted-foreground" />
              </Link>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
