"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowLeft, CheckCircle2, Loader2, Mail } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Logo } from "@/components/site/logo";
import { api } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [submitting, setSubmitting] = React.useState(false);
  const [done, setDone] = React.useState(false);
  const [email, setEmail] = React.useState("");

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await api("/auth/forgot-password", {
        method: "POST",
        body: JSON.stringify({ email: email.trim().toLowerCase() }),
      });
    } catch {
      // Always show "done" so we don't disclose email existence.
    } finally {
      setSubmitting(false);
      setDone(true);
    }
  }

  return (
    <div className="min-h-svh bg-background flex flex-col">
      <header className="container-page py-6">
        <Logo />
      </header>
      <main className="flex-1 container-page flex items-center justify-center py-12">
        <div className="w-full max-w-md">
          <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-soft text-primary">
            <Mail className="h-5 w-5" />
          </div>
          <h1 className="mt-5 text-2xl font-semibold tracking-tight">Forgot your password?</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Enter your work email and we&apos;ll send you a link to reset it.
            The link expires in 30 minutes.
          </p>

          {done ? (
            <div className="mt-8 rounded-2xl border border-emerald-200 bg-emerald-50 p-6">
              <CheckCircle2 className="h-5 w-5 text-emerald-700" />
              <div className="mt-3 text-sm font-semibold text-emerald-900">
                Check your inbox.
              </div>
              <p className="mt-1 text-sm text-emerald-900/80">
                If an account exists for {email}, a reset link is on its way. It
                may take a minute.
              </p>
              <Button variant="outline" className="mt-4" asChild>
                <Link href="/admin/login">
                  <ArrowLeft className="h-4 w-4" /> Back to sign in
                </Link>
              </Button>
            </div>
          ) : (
            <form onSubmit={onSubmit} className="mt-8 grid gap-4">
              <div className="grid gap-2">
                <Label htmlFor="email">Work email</Label>
                <Input
                  id="email"
                  type="email"
                  required
                  autoFocus
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@quatadigital.com"
                />
              </div>
              <Button type="submit" disabled={submitting} size="lg">
                {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                Send reset link
              </Button>
              <Link
                href="/admin/login"
                className="text-sm text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
              >
                <ArrowLeft className="h-3.5 w-3.5" /> Back to sign in
              </Link>
            </form>
          )}
        </div>
      </main>
    </div>
  );
}
