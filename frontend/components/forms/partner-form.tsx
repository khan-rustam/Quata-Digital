"use client";

import * as React from "react";
import { CheckCircle2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import type { FormField, PartnerType } from "@/lib/partner-types";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import { HCaptcha, captchaConfigured } from "@/components/site/hcaptcha";

export function PartnerForm({
  type,
  fields,
  cta,
}: {
  type: PartnerType;
  fields: FormField[];
  cta: string;
}) {
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
    const form = new FormData(e.currentTarget);
    const data: Record<string, FormDataEntryValue> = {};
    form.forEach((v, k) => (data[k] = v));
    try {
      await api(`/partners/${type}`, {
        method: "POST",
        body: JSON.stringify({ payload: data, captcha_token: captchaToken }),
      });
      setSuccess(true);
      (e.target as HTMLFormElement).reset();
      setCaptchaToken(null);
      toast.success("Application received", "We'll be in touch shortly.");
    } catch (err) {
      toast.error(
        "Couldn't submit",
        err instanceof Error ? err.message : "Please try again.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  if (success) {
    return (
      <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-8 text-center">
        <CheckCircle2 className="mx-auto h-10 w-10 text-emerald-700" />
        <div className="mt-4 text-lg font-semibold text-emerald-900">
          Application received.
        </div>
        <p className="mt-2 text-sm text-emerald-900/80 max-w-md mx-auto">
          A QUATA partnerships lead will review and reach out shortly. You can
          submit another application below.
        </p>
        <Button
          variant="outline"
          className="mt-5"
          onClick={() => setSuccess(false)}
        >
          Submit another
        </Button>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="grid gap-4 sm:gap-5">
      {fields.map((f) => (
        <div key={f.name} className="grid gap-2">
          <Label htmlFor={f.name}>
            {f.label}
            {f.required && <span className="text-destructive"> *</span>}
          </Label>
          {f.type === "textarea" ? (
            <Textarea
              id={f.name}
              name={f.name}
              placeholder={f.placeholder}
              required={f.required}
            />
          ) : f.type === "select" ? (
            <Select id={f.name} name={f.name} required={f.required} defaultValue="">
              <option value="" disabled>
                Select…
              </option>
              {f.options?.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </Select>
          ) : (
            <Input
              id={f.name}
              name={f.name}
              type={f.type}
              placeholder={f.placeholder}
              required={f.required}
            />
          )}
        </div>
      ))}
      <HCaptcha onVerify={setCaptchaToken} onExpire={() => setCaptchaToken(null)} />
      <div>
        <Button size="lg" type="submit" disabled={submitting}>
          {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          {cta}
        </Button>
        <p className="mt-3 text-xs text-muted-foreground">
          By submitting you agree to QUATA&apos;s privacy policy. We&apos;ll only use
          this information to evaluate the partnership.
        </p>
      </div>
    </form>
  );
}
