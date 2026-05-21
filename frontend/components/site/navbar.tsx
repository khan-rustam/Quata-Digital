"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, X, ArrowRight, Search } from "lucide-react";
import { Logo } from "./logo";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const links = [
  { href: "/ecosystem", label: "Ecosystem" },
  { href: "/partners", label: "Partners" },
  { href: "/careers", label: "Careers" },
  { href: "/blog", label: "News" },
  { href: "/about", label: "About" },
  { href: "/contact", label: "Contact" },
];

export function Navbar() {
  const pathname = usePathname();
  const [open, setOpen] = React.useState(false);
  const [scrolled, setScrolled] = React.useState(false);

  React.useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- close mobile menu when route changes.
    setOpen(false);
  }, [pathname]);

  // Escape closes the mobile menu — keyboard users couldn't dismiss it
  // otherwise. Lock body scroll while it's open so the underlying page
  // doesn't shift beneath the overlay.
  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [open]);

  return (
    <header
      className={cn(
        "sticky top-0 z-40 w-full transition-all duration-300",
        scrolled ? "py-3" : "py-0"
      )}
    >
      <div className="container-page">
        <div
          className={cn(
            "flex items-center justify-between transition-all duration-300",
            scrolled
              ? "h-16 px-4 md:px-6 rounded-full border border-border bg-surface/85 backdrop-blur-xl shadow-[0_8px_30px_-12px_rgba(15,18,22,0.18),0_2px_6px_rgba(15,18,22,0.06),inset_0_1px_0_rgba(255,255,255,0.6)]"
              : "h-20 bg-transparent border border-transparent"
          )}
        >
          <div className="flex items-center gap-8">
            <Logo size={scrolled ? "md" : "lg"} />
            <nav className="hidden md:flex items-center gap-1">
              {links.map((link) => {
                const active =
                  pathname === link.href || pathname.startsWith(link.href + "/");
                return (
                  <Link
                    key={link.href}
                    href={link.href}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "rounded-full px-3 py-1.5 text-sm transition-colors",
                      active
                        ? "text-foreground bg-secondary"
                        : "text-muted-foreground hover:text-foreground hover:bg-secondary/60"
                    )}
                  >
                    {link.label}
                  </Link>
                );
              })}
            </nav>
          </div>
          <div className="hidden md:flex items-center gap-2">
            <Link
              href="/search"
              aria-label="Search"
              className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-border bg-surface text-muted-foreground hover:text-foreground hover:bg-secondary"
            >
              <Search className="h-4 w-4" />
            </Link>
            <Button variant="ghost" asChild>
              <Link href="/admin/login">Sign in</Link>
            </Button>
            <Button asChild>
              <Link href="/partners">
                Become a partner <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          </div>
          <button
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            aria-controls="mobile-nav"
            onClick={() => setOpen((v) => !v)}
            className="md:hidden inline-flex h-10 w-10 items-center justify-center rounded-full border border-border bg-surface"
          >
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {open && (
        <div
          id="mobile-nav"
          className="md:hidden mt-2 mx-4 rounded-2xl border border-border bg-surface shadow-[0_8px_30px_-12px_rgba(15,18,22,0.18)]"
        >
          <nav className="px-4 py-3 grid gap-1">
            {links.map((link) => {
              const active =
                pathname === link.href || pathname.startsWith(link.href + "/");
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "rounded-lg px-3 py-2.5 text-sm hover:bg-secondary",
                    active && "bg-secondary font-medium"
                  )}
                >
                  {link.label}
                </Link>
              );
            })}
            <div className="flex items-center gap-2 pt-2">
              <Button variant="outline" asChild className="flex-1">
                <Link href="/admin/login">Sign in</Link>
              </Button>
              <Button asChild className="flex-1">
                <Link href="/partners">Become a partner</Link>
              </Button>
            </div>
          </nav>
        </div>
      )}
    </header>
  );
}
