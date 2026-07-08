"use client";

import * as React from "react";
import { CalendarClock, CalendarCheck, Download, Eye, Loader2, Mail, Phone } from "lucide-react";
import { SlideOver, SlideOverContent } from "@/components/admin/slide-over";
import { FormDialog } from "@/components/admin/form-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useApi, useApiAction } from "@/lib/use-api";
import { apiUrl } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/components/ui/toast";

type AppDetail = {
  id: number;
  full_name: string;
  email: string;
  phone: string | null;
  has_resume: boolean;
  cover_letter: string | null;
  status: "new" | "shortlisted" | "interviewed" | "rejected" | "hired";
  job_title: string | null;
  interview_at: string | null;
  interview_location: string | null;
  start_date: string | null;
  created_at: string;
  updated_at: string;
};

const variant: Record<AppDetail["status"], "default" | "warn" | "success" | "danger" | "brand"> = {
  new: "default",
  shortlisted: "brand",
  interviewed: "warn",
  rejected: "danger",
  hired: "success",
};

const DEFAULT_DOCUMENTS =
  "• Valid national ID card or passport\n• Original and photocopies of your academic certificates\n• Any relevant work samples, portfolio or references";
const DEFAULT_INTERVIEW_LOCATION = "QUATA Digital Enterprise office, Bamenda, Cameroon";

function fmtDateTime(s: string | null): string | null {
  if (!s) return null;
  const d = new Date(s);
  return isNaN(d.getTime()) ? s : d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function fmtDate(s: string | null): string | null {
  if (!s) return null;
  const d = new Date(`${s}T00:00:00`);
  return isNaN(d.getTime()) ? s : d.toLocaleDateString(undefined, { dateStyle: "medium" });
}

// Open the browser's native date/time calendar on click — the built-in
// picker icon is easy to miss, so clicking anywhere on the field pops it.
function openNativePicker(e: React.MouseEvent<HTMLInputElement>) {
  const el = e.currentTarget;
  if ("showPicker" in el) {
    try {
      el.showPicker();
    } catch {
      /* showPicker requires user activation; the click qualifies, but guard
         against browser quirks so nothing throws */
    }
  }
}

export function ApplicationDetailSlideOver({
  open,
  onOpenChange,
  applicationId,
  onChanged,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  applicationId: number | null;
  onChanged: () => void;
}) {
  const path = open && applicationId ? `/admin/applications/${applicationId}` : null;
  const { data, loading } = useApi<AppDetail>(path);
  const action = useApiAction();
  const toast = useToast();
  const { token } = useAuth();
  const [downloading, setDownloading] = React.useState(false);
  const [viewing, setViewing] = React.useState(false);
  const [shortlistOpen, setShortlistOpen] = React.useState(false);
  const [hireOpen, setHireOpen] = React.useState(false);
  const [rejectOpen, setRejectOpen] = React.useState(false);

  // --- Private CV: fetch through the authenticated endpoint (Q1) ---
  async function fetchResumeBlob(): Promise<{ blob: Blob; filename: string }> {
    const res = await fetch(`${apiUrl}/admin/applications/${applicationId}/resume`, {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    });
    if (!res.ok) throw new Error(`Request failed (${res.status})`);
    const cd = res.headers.get("Content-Disposition") ?? "";
    const filename = cd.match(/filename="?([^"]+)"?/)?.[1] ?? `resume-${applicationId}`;
    return { blob: await res.blob(), filename };
  }

  async function viewResume() {
    if (!applicationId) return;
    // Reserve the tab inside the click gesture so the popup blocker allows it.
    const win = window.open("", "_blank");
    setViewing(true);
    try {
      const { blob } = await fetchResumeBlob();
      const url = URL.createObjectURL(blob);
      if (win) win.location.href = url;
      else window.location.href = url; // popup blocked — same-tab fallback
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (err) {
      if (win) win.close();
      toast.error("Couldn't open resume", err instanceof Error ? err.message : "Try again.");
    } finally {
      setViewing(false);
    }
  }

  async function downloadResume() {
    if (!applicationId) return;
    setDownloading(true);
    try {
      const { blob, filename } = await fetchResumeBlob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      toast.error("Couldn't download resume", err instanceof Error ? err.message : "Try again.");
    } finally {
      setDownloading(false);
    }
  }

  // --- Status transitions ---
  async function patchStatus(body: Record<string, unknown>, successMsg: string, close?: () => void) {
    if (!applicationId) return;
    try {
      await action(`/admin/applications/${applicationId}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      toast.success(successMsg);
      close?.();
      onChanged();
    } catch (err) {
      toast.error("Couldn't update", err instanceof Error ? err.message : "Try again.");
    }
  }

  async function submitShortlist(form: FormData) {
    const dateStr = String(form.get("interview_date") || "");
    const timeStr = String(form.get("interview_time") || "09:00");
    const notify = form.get("notify") === "on";
    await patchStatus(
      {
        status: "shortlisted",
        // Naive local wall-clock (no tz suffix) so the time the admin picks is
        // exactly what the candidate sees — no UTC shifting.
        interview_at: dateStr ? `${dateStr}T${timeStr}:00` : null,
        interview_location: String(form.get("interview_location") || "").trim() || null,
        documents: String(form.get("documents") || "").trim() || null,
        message: String(form.get("message") || "").trim() || null,
        notify,
      },
      notify ? "Shortlisted — email sent to the candidate" : "Marked shortlisted",
      () => setShortlistOpen(false),
    );
  }

  async function submitHire(form: FormData) {
    const notify = form.get("notify") === "on";
    await patchStatus(
      {
        status: "hired",
        start_date: String(form.get("start_date") || "").trim() || null,
        message: String(form.get("message") || "").trim() || null,
        notify,
      },
      notify ? "Hired — offer email sent to the candidate" : "Marked hired",
      () => setHireOpen(false),
    );
  }

  async function submitReject(form: FormData) {
    const notify = form.get("notify") === "on";
    await patchStatus(
      {
        status: "rejected",
        message: String(form.get("message") || "").trim() || null,
        notify,
      },
      notify ? "Rejected — email sent to the candidate" : "Marked rejected",
      () => setRejectOpen(false),
    );
  }

  const interviewWhen = data ? fmtDateTime(data.interview_at) : null;
  const startWhen = data ? fmtDate(data.start_date) : null;

  return (
    <>
      <SlideOver open={open} onOpenChange={onOpenChange}>
        <SlideOverContent
          title={data ? data.full_name : "Application"}
          description={data ? `${data.job_title ?? "—"} · submitted ${new Date(data.created_at).toLocaleString()}` : ""}
          size="lg"
        >
          {loading || !data ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <div className="space-y-6">
              {/* Status + actions */}
              <div className="rounded-2xl border border-border bg-surface-soft p-4">
                <div className="flex items-center justify-between gap-3">
                  <Badge variant={variant[data.status]} className="capitalize">{data.status}</Badge>
                  <div className="flex gap-1.5 flex-wrap justify-end">
                    <Button size="sm" variant="ghost" onClick={() => setShortlistOpen(true)}>Shortlist</Button>
                    <Button size="sm" variant="ghost" onClick={() => patchStatus({ status: "interviewed", notify: false }, "Marked interviewed")}>Interviewed</Button>
                    <Button size="sm" onClick={() => setHireOpen(true)}>Hire</Button>
                    <Button size="sm" variant="ghost" className="text-rose-700" onClick={() => setRejectOpen(true)}>
                      Reject
                    </Button>
                  </div>
                </div>

                {/* Scheduling — reflects what was sent to the candidate */}
                {(interviewWhen || startWhen) && (
                  <div className="mt-4 grid gap-2 border-t border-border/60 pt-3 text-sm">
                    {interviewWhen && (
                      <div className="flex items-start gap-2 text-foreground/85">
                        <CalendarClock className="h-4 w-4 text-primary mt-0.5 shrink-0" />
                        <span>
                          Interview: <span className="font-medium">{interviewWhen}</span>
                          {data.interview_location && (
                            <span className="text-muted-foreground"> · {data.interview_location}</span>
                          )}
                        </span>
                      </div>
                    )}
                    {startWhen && (
                      <div className="flex items-center gap-2 text-foreground/85">
                        <CalendarCheck className="h-4 w-4 text-emerald-600 shrink-0" />
                        <span>Start date: <span className="font-medium">{startWhen}</span></span>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Contact */}
              <div className="grid sm:grid-cols-2 gap-3">
                <a
                  href={`mailto:${data.email}`}
                  className="rounded-xl border border-border bg-card p-4 hover:bg-surface-soft transition flex items-center gap-3"
                >
                  <Mail className="h-4 w-4 text-primary" />
                  <div className="min-w-0">
                    <div className="text-xs uppercase tracking-wider text-muted-foreground">Email</div>
                    <div className="text-sm font-medium truncate">{data.email}</div>
                  </div>
                </a>
                {data.phone && (
                  <a
                    href={`tel:${data.phone}`}
                    className="rounded-xl border border-border bg-card p-4 hover:bg-surface-soft transition flex items-center gap-3"
                  >
                    <Phone className="h-4 w-4 text-primary" />
                    <div className="min-w-0">
                      <div className="text-xs uppercase tracking-wider text-muted-foreground">Phone</div>
                      <div className="text-sm font-medium truncate">{data.phone}</div>
                    </div>
                  </a>
                )}
              </div>

              {/* Resume — private CV: view inline or download, both auth-gated */}
              <div>
                <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Resume</div>
                {data.has_resume ? (
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={viewResume}
                      disabled={viewing}
                      className="inline-flex items-center gap-2 rounded-xl border border-border bg-card px-4 py-3 text-sm hover:bg-surface-soft transition disabled:opacity-60"
                    >
                      {viewing ? <Loader2 className="h-4 w-4 text-primary animate-spin" /> : <Eye className="h-4 w-4 text-primary" />}
                      {viewing ? "Opening…" : "View CV"}
                    </button>
                    <button
                      type="button"
                      onClick={downloadResume}
                      disabled={downloading}
                      className="inline-flex items-center gap-2 rounded-xl border border-border bg-card px-4 py-3 text-sm hover:bg-surface-soft transition disabled:opacity-60"
                    >
                      {downloading ? <Loader2 className="h-4 w-4 text-primary animate-spin" /> : <Download className="h-4 w-4 text-primary" />}
                      {downloading ? "Preparing…" : "Download CV"}
                    </button>
                  </div>
                ) : (
                  <div className="text-sm text-muted-foreground">No CV attached.</div>
                )}
              </div>

              {/* Cover letter */}
              {data.cover_letter && (
                <div>
                  <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                    Cover letter
                  </div>
                  <div className="rounded-xl border border-border bg-card p-4 text-sm whitespace-pre-line text-foreground/85">
                    {data.cover_letter}
                  </div>
                </div>
              )}
            </div>
          )}
        </SlideOverContent>
      </SlideOver>

      {/* Shortlist → invite to interview */}
      <FormDialog
        open={shortlistOpen}
        onOpenChange={setShortlistOpen}
        title="Shortlist & invite to interview"
        description="Sends the candidate an email with the interview details and documents to bring."
        submitLabel="Shortlist & send email"
        onSubmit={submitShortlist}
      >
        <div className="grid grid-cols-2 gap-3">
          <div className="grid gap-1.5">
            <Label htmlFor="interview_date">Interview date</Label>
            <Input id="interview_date" name="interview_date" type="date" required onClick={openNativePicker} className="cursor-pointer" />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="interview_time">Time</Label>
            <Input id="interview_time" name="interview_time" type="time" defaultValue="09:00" required onClick={openNativePicker} className="cursor-pointer" />
          </div>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="interview_location">Location</Label>
          <Input id="interview_location" name="interview_location" defaultValue={DEFAULT_INTERVIEW_LOCATION} />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="documents">Documents to bring</Label>
          <Textarea id="documents" name="documents" rows={4} defaultValue={DEFAULT_DOCUMENTS} />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="sl_message">Extra note (optional)</Label>
          <Textarea id="sl_message" name="message" rows={2} placeholder="Anything else you'd like to add to the email." />
        </div>
        <label className="flex items-center gap-2 text-sm text-foreground/85">
          <input type="checkbox" name="notify" defaultChecked className="h-4 w-4 rounded border-border" />
          Email the candidate now (copied to careers@quatadigital.com)
        </label>
      </FormDialog>

      {/* Hire → make offer */}
      <FormDialog
        open={hireOpen}
        onOpenChange={setHireOpen}
        title="Hire candidate"
        description="Sends the candidate an offer email with their start date."
        submitLabel="Hire & send offer"
        onSubmit={submitHire}
      >
        <div className="grid gap-1.5">
          <Label htmlFor="start_date">Start date</Label>
          <Input id="start_date" name="start_date" type="date" required onClick={openNativePicker} className="cursor-pointer" />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="hire_message">Message (optional)</Label>
          <Textarea id="hire_message" name="message" rows={3} placeholder="Onboarding details, who to report to, etc." />
        </div>
        <label className="flex items-center gap-2 text-sm text-foreground/85">
          <input type="checkbox" name="notify" defaultChecked className="h-4 w-4 rounded border-border" />
          Email the candidate now (copied to careers@quatadigital.com)
        </label>
      </FormDialog>

      {/* Reject → polite decline */}
      <FormDialog
        open={rejectOpen}
        onOpenChange={setRejectOpen}
        title="Reject candidate"
        description="Sends the candidate a courteous email. Leave the message blank to use the standard polite note."
        submitLabel="Reject & send email"
        onSubmit={submitReject}
      >
        <div className="grid gap-1.5">
          <Label htmlFor="reject_message">Custom message (optional)</Label>
          <Textarea
            id="reject_message"
            name="message"
            rows={4}
            placeholder="Leave blank to send the standard courteous rejection note."
          />
        </div>
        <label className="flex items-center gap-2 text-sm text-foreground/85">
          <input type="checkbox" name="notify" defaultChecked className="h-4 w-4 rounded border-border" />
          Email the candidate now (copied to careers@quatadigital.com)
        </label>
      </FormDialog>
    </>
  );
}
