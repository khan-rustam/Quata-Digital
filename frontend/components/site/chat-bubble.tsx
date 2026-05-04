"use client";

import * as React from "react";
import { MessageCircle, X, Mail, Send } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Internally-built live-chat placeholder.
 *
 * Renders a floating bubble in the bottom-right of the marketing site. When
 * opened it shows a friendly card with the public support emails — and a
 * stub composer that posts via mailto: until the real chat backend is wired
 * in. This is intentionally lightweight so the experience stays fast.
 */
export function ChatBubble() {
  const [open, setOpen] = React.useState(false);
  const [message, setMessage] = React.useState("");

  function handleOpen(next: boolean) {
    setOpen(next);
  }

  function handleSend(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const body = encodeURIComponent(message.trim() || "Hi QUATA team,");
    window.location.href = `mailto:info@quatadigital.com?subject=${encodeURIComponent(
      "Chat from quatadigital.com"
    )}&body=${body}`;
  }

  return (
    <>
      <button
        type="button"
        aria-label={open ? "Close chat" : "Open chat"}
        onClick={() => handleOpen(!open)}
        className={cn(
          "fixed bottom-4 right-4 z-40 inline-flex h-12 w-12 items-center justify-center rounded-full shadow-xl transition-all",
          "bg-primary text-primary-foreground hover:scale-105",
          open ? "rotate-90" : "rotate-0"
        )}
      >
        {open ? <X className="h-5 w-5" /> : <MessageCircle className="h-5 w-5" />}
      </button>

      {open && (
        <div className="fixed bottom-20 right-4 z-40 w-[calc(100vw-2rem)] sm:w-80 rounded-2xl border border-border bg-card shadow-2xl ring-elevated overflow-hidden">
          <div className="bg-linear-to-br from-primary to-emerald-500 p-4 text-white">
            <div className="flex items-center gap-3">
              <div className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-white/15 text-white text-base font-bold tracking-tight ring-1 ring-white/20 shrink-0">
                Q
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-300">
                    <span className="absolute inset-0 rounded-full bg-emerald-300 opacity-60 animate-ping" />
                  </span>
                  <div className="text-sm font-semibold">QUATA Digital</div>
                </div>
                <div className="text-[11px] text-white/70">
                  Bamenda, Cameroon
                </div>
              </div>
            </div>
            <div className="mt-3 text-xs text-white/85">
              Live chat is rolling out alongside our launch. Drop us a note —
              we read everything that comes through.
            </div>
          </div>

          <div className="p-4 space-y-3 text-sm">
            <a
              href="mailto:info@quatadigital.com"
              className="flex items-center gap-3 rounded-xl border border-border p-3 hover:bg-surface-soft transition"
            >
              <Mail className="h-4 w-4 text-primary shrink-0" />
              <div className="min-w-0">
                <div className="text-xs font-semibold">General &amp; partnerships</div>
                <div className="text-xs text-muted-foreground truncate">
                  info@quatadigital.com
                </div>
              </div>
            </a>
            <a
              href="mailto:support@quatadigital.com"
              className="flex items-center gap-3 rounded-xl border border-border p-3 hover:bg-surface-soft transition"
            >
              <Mail className="h-4 w-4 text-primary shrink-0" />
              <div className="min-w-0">
                <div className="text-xs font-semibold">Customer support</div>
                <div className="text-xs text-muted-foreground truncate">
                  support@quatadigital.com
                </div>
              </div>
            </a>

            <form onSubmit={handleSend} className="grid gap-2">
              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                rows={3}
                placeholder="Type your message…"
                className="w-full rounded-lg border border-input bg-surface px-3 py-2 text-xs outline-none focus:ring-2 focus:ring-ring"
              />
              <button
                type="submit"
                className="inline-flex items-center justify-center gap-1.5 rounded-full bg-primary text-primary-foreground px-3 py-1.5 text-xs font-medium hover:bg-primary/90"
              >
                <Send className="h-3 w-3" /> Send via email
              </button>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
