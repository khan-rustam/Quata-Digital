"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { Loader2, Mail, CheckCircle2, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { HCaptcha, captchaConfigured } from "@/components/site/hcaptcha";

export function NewsletterSignup({
  title = "Get the inside line on what we ship.",
  subtitle = "Monthly updates from the QUATA team — no fluff, no pitches.",
  source = "footer",
}: {
  title?: string;
  subtitle?: string;
  source?: string;
}) {
  const [submitting, setSubmitting] = React.useState(false);
  const [done, setDone] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [captchaToken, setCaptchaToken] = React.useState<string | null>(null);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    const data = new FormData(e.currentTarget);
    const email = String(data.get("email") || "").trim();
    if (!email) return;
    if (captchaConfigured && !captchaToken) {
      setError("Please complete the captcha first.");
      return;
    }
    setSubmitting(true);
    try {
      await api("/newsletter/subscribe", {
        method: "POST",
        body: JSON.stringify({ email, source, captcha_token: captchaToken }),
      });
      setDone(true);
      setCaptchaToken(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      className="relative overflow-hidden rounded-3xl border border-border bg-surface-soft p-6 sm:p-8 md:p-10"
    >
      <div
        className="absolute -top-32 -right-32 h-72 w-72 rounded-full opacity-30 blur-3xl"
        style={{ background: "radial-gradient(closest-side, rgba(14,91,74,0.5), transparent)" }}
      />
      <div className="grid md:grid-cols-2 gap-6 items-center relative">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1 text-xs">
            <Mail className="h-3.5 w-3.5 text-primary" /> Newsletter
          </div>
          <h3 className="mt-3 text-xl sm:text-2xl md:text-3xl font-semibold tracking-tight text-balance">
            {title}
          </h3>
          <p className="mt-2 text-sm text-muted-foreground max-w-md">{subtitle}</p>
        </div>
        {done ? (
          <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5 text-emerald-900 flex items-center gap-3">
            <CheckCircle2 className="h-5 w-5" />
            <div>
              <div className="text-sm font-semibold">You&apos;re in.</div>
              <div className="text-xs">First issue lands in your inbox soon.</div>
            </div>
          </div>
        ) : (
          <form onSubmit={onSubmit} className="flex flex-col gap-2">
            <div className="flex flex-col sm:flex-row gap-2">
              <Input
                type="email"
                required
                name="email"
                placeholder="you@company.com"
                className="bg-surface"
                disabled={submitting}
              />
              <Button type="submit" disabled={submitting} className="sm:w-auto">
                {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                Subscribe
              </Button>
            </div>
            <HCaptcha
              onVerify={setCaptchaToken}
              onExpire={() => setCaptchaToken(null)}
            />
            {error && (
              <div className="flex items-center gap-2 text-xs text-rose-700">
                <AlertCircle className="h-3.5 w-3.5" />
                {error}
              </div>
            )}
          </form>
        )}
      </div>
    </motion.div>
  );
}
