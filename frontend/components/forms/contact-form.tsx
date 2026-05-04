"use client";

import * as React from "react";
import { CheckCircle2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import { HCaptcha, captchaConfigured } from "@/components/site/hcaptcha";

const reasons = [
  "General enquiry",
  "Press / media",
  "Partnerships",
  "Investor relations",
  "Customer support",
  "Other",
];

export function ContactForm() {
  const [submitting, setSubmitting] = React.useState(false);
  const [success, setSuccess] = React.useState(false);
  const [captchaToken, setCaptchaToken] = React.useState<string | null>(null);
  const toast = useToast();

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (captchaConfigured && !captchaToken) {
      toast.error("Captcha required", "Please complete the captcha first.");
      return;
    }
    setSubmitting(true);
    const data = Object.fromEntries(new FormData(e.currentTarget).entries());
    try {
      await api("/contact", {
        method: "POST",
        body: JSON.stringify({ ...data, captcha_token: captchaToken }),
      });
      setSuccess(true);
      (e.target as HTMLFormElement).reset();
      setCaptchaToken(null);
      toast.success("Message sent", "We'll be in touch shortly.");
    } catch (err) {
      toast.error("Couldn't send", err instanceof Error ? err.message : "Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (success) {
    return (
      <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-6 text-center">
        <CheckCircle2 className="mx-auto h-8 w-8 text-emerald-700" />
        <div className="mt-3 text-base font-semibold text-emerald-900">
          Message sent.
        </div>
        <p className="mt-1 text-sm text-emerald-900/80">
          We&apos;ll get back to you shortly.
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="grid gap-4">
      <div className="grid gap-2">
        <Label htmlFor="name">Name *</Label>
        <Input id="name" name="name" required />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="email">Email *</Label>
        <Input id="email" name="email" type="email" required />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="company">Company</Label>
        <Input id="company" name="company" />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="reason">Reason *</Label>
        <Select id="reason" name="reason" required defaultValue="">
          <option value="" disabled>
            Select…
          </option>
          {reasons.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </Select>
      </div>
      <div className="grid gap-2">
        <Label htmlFor="message">Message *</Label>
        <Textarea id="message" name="message" rows={5} required />
      </div>
      <HCaptcha onVerify={setCaptchaToken} onExpire={() => setCaptchaToken(null)} />
      <div>
        <Button type="submit" disabled={submitting} size="lg">
          {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          Send message
        </Button>
      </div>
    </form>
  );
}
