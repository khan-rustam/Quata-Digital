"use client";

import * as React from "react";
import { CheckCircle2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { FileUpload } from "@/components/forms/file-upload";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { HCaptcha, captchaConfigured } from "@/components/site/hcaptcha";

export function JobApplicationForm({ jobId }: { jobId: number }) {
  const [submitting, setSubmitting] = React.useState(false);
  const [success, setSuccess] = React.useState(false);
  const [captchaToken, setCaptchaToken] = React.useState<string | null>(null);
  const toast = useToast();

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    const form = new FormData(e.currentTarget);
    const data = Object.fromEntries(form.entries());
    if (!data.resume_url) {
      toast.error("Resume required", "Please upload your resume before submitting.");
      setSubmitting(false);
      return;
    }
    if (captchaConfigured && !captchaToken) {
      toast.error("Captcha required", "Please complete the captcha first.");
      setSubmitting(false);
      return;
    }
    try {
      await api(`/jobs/${jobId}/apply`, {
        method: "POST",
        body: JSON.stringify({ ...data, captcha_token: captchaToken }),
      });
      setSuccess(true);
      (e.target as HTMLFormElement).reset();
      setCaptchaToken(null);
      toast.success("Application sent", "We'll be in touch if there's a fit.");
    } catch (err) {
      toast.error("Couldn't submit", err instanceof Error ? err.message : "Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (success) {
    return (
      <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-6 text-center">
        <CheckCircle2 className="mx-auto h-8 w-8 text-emerald-700" />
        <div className="mt-3 text-base font-semibold text-emerald-900">
          Application submitted.
        </div>
        <p className="mt-1 text-sm text-emerald-900/80">
          We&apos;ll be in touch if there&apos;s a fit.
        </p>
        <Button variant="outline" className="mt-4" onClick={() => setSuccess(false)}>
          Submit another
        </Button>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="grid gap-4">
      <div className="grid gap-2">
        <Label htmlFor="full_name">Full name *</Label>
        <Input id="full_name" name="full_name" required />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="email">Email *</Label>
        <Input id="email" name="email" type="email" required />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="phone">Phone</Label>
        <Input id="phone" name="phone" type="tel" />
      </div>
      <div className="grid gap-2">
        <Label>Resume / CV *</Label>
        <FileUpload
          name="resume_url"
          folder="resumes"
          endpoint="/uploads/public"
          accept=".pdf,.doc,.docx,.rtf,.txt"
          hint="PDF or Word — up to 25 MB"
        />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="cover_letter">Why this role?</Label>
        <Textarea id="cover_letter" name="cover_letter" rows={5} />
      </div>
      <HCaptcha onVerify={setCaptchaToken} onExpire={() => setCaptchaToken(null)} />
      <div>
        <Button type="submit" disabled={submitting} size="lg">
          {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          Submit application
        </Button>
      </div>
    </form>
  );
}
