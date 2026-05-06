"use client";

import * as React from "react";
import Link from "next/link";
import {
  ArrowLeft,
  CheckCircle2,
  Loader2,
  Mail,
  Send,
  Users,
  AlertTriangle,
  History,
} from "lucide-react";

import { PageShell } from "@/components/admin/page-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useApi, useApiAction } from "@/lib/use-api";
import { useToast } from "@/components/ui/toast";
import { MarkdownEditor } from "@/components/admin/markdown-editor";
import { formatDate } from "@/lib/utils";

type SubscriberSummary = {
  total: number;
  active: number;
  items: unknown[];
};

type BroadcastResult = {
  id: number;
  subject: string;
  recipients_count: number;
  delivered: number;
  failed: number;
  status: "sent" | "failed" | "pending";
  sent_at: string | null;
  error_summary: string | null;
  test_only: boolean;
};

type BroadcastHistory = {
  id: number;
  subject: string;
  recipients_count: number;
  delivered_count: number;
  failed_count: number;
  status: string;
  sent_at: string | null;
  created_at: string;
  sender: string;
  error_summary: string | null;
};

export default function NewsletterBroadcastPage() {
  return (
    <PageShell
      title="Send a newsletter"
      description="Compose a newsletter and send it to every active subscriber. The broadcast is recorded in the audit trail."
      requirePermission="newsletter:manage"
    >
      <BroadcastBody />
    </PageShell>
  );
}

function BroadcastBody() {
  const action = useApiAction();
  const toast = useToast();

  const { data: subs } = useApi<SubscriberSummary>("/admin/newsletter?limit=1");
  const { data: history, refresh: refreshHistory } =
    useApi<BroadcastHistory[]>("/admin/newsletter/broadcasts");

  const [subject, setSubject] = React.useState("");
  const [body, setBody] = React.useState("");
  const [testEmail, setTestEmail] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [confirmSend, setConfirmSend] = React.useState(false);
  const [lastResult, setLastResult] = React.useState<BroadcastResult | null>(null);

  const activeSubs = subs?.active ?? 0;

  const canSend = subject.trim().length > 0 && body.trim().length > 0;

  async function send(opts: { test: boolean }) {
    setSubmitting(true);
    setLastResult(null);
    try {
      const res = await action<BroadcastResult>("/admin/newsletter/broadcast", {
        method: "POST",
        body: JSON.stringify({
          subject,
          body,
          test_email: opts.test ? testEmail.trim() : null,
        }),
      });
      setLastResult(res);
      if (opts.test) {
        toast.success("Test sent", `Preview emailed to ${testEmail}.`);
      } else {
        toast.success(
          "Broadcast sent",
          `${res.delivered} delivered · ${res.failed} failed.`,
        );
        // Don't clear the compose box — let the boss verify what was sent.
        refreshHistory();
      }
    } catch (err) {
      toast.error("Couldn't send", err instanceof Error ? err.message : "Try again.");
    } finally {
      setSubmitting(false);
      setConfirmSend(false);
    }
  }

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="outline" size="sm" asChild>
          <Link href="/admin/newsletter">
            <ArrowLeft className="h-3.5 w-3.5" /> Subscribers
          </Link>
        </Button>
        <span className="inline-flex items-center gap-2 rounded-full bg-brand-soft text-primary px-3 py-1 text-xs font-medium">
          <Users className="h-3 w-3" />
          {activeSubs} active subscriber{activeSubs === 1 ? "" : "s"}
        </span>
      </div>

      <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
        {/* Compose */}
        <div className="rounded-2xl border border-border bg-card p-6 ring-soft grid gap-4">
          <div className="grid gap-1.5">
            <Label htmlFor="subject">Subject</Label>
            <Input
              id="subject"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="What this issue is about — keep it short."
              maxLength={255}
            />
          </div>
          <div className="grid gap-1.5">
            <Label>Body</Label>
            <MarkdownEditor
              value={body}
              onChange={setBody}
              placeholder="Write the newsletter in markdown. Two newlines start a new paragraph."
              rows={16}
              imageFolder="newsletter"
              defaultMode="split"
            />
            <div className="text-xs text-muted-foreground">
              The body is sent as plain text. Most modern mail clients will render
              links and basic formatting. Images are uploaded to the QUATA server
              and inserted as markdown so they survive forwarding.
            </div>
          </div>
        </div>

        {/* Side panel: test send + send to all */}
        <aside className="grid gap-4">
          <div className="rounded-2xl border border-border bg-card p-5 ring-soft">
            <div className="text-sm font-semibold">Send a test first</div>
            <div className="mt-1 text-xs text-muted-foreground">
              Email yourself the broadcast to make sure the subject + body look
              right before going to everyone.
            </div>
            <div className="mt-4 grid gap-2">
              <Input
                type="email"
                value={testEmail}
                onChange={(e) => setTestEmail(e.target.value)}
                placeholder="you@quatadigital.com"
              />
              <Button
                variant="outline"
                onClick={() => send({ test: true })}
                disabled={
                  submitting ||
                  !canSend ||
                  testEmail.trim().length < 4 ||
                  !testEmail.includes("@")
                }
              >
                {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Mail className="h-4 w-4" />}
                Send test
              </Button>
            </div>
          </div>

          <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5">
            <div className="flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 mt-0.5 text-amber-700 shrink-0" />
              <div className="text-xs text-amber-900">
                <strong>Sending to everyone is irreversible.</strong> Confirm
                you&apos;re happy with the subject + body, then click below.
                The broadcast is recorded in the audit trail.
              </div>
            </div>
            <Button
              className="mt-4 w-full"
              onClick={() => setConfirmSend(true)}
              disabled={submitting || !canSend || activeSubs === 0}
            >
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              Send to {activeSubs} subscriber{activeSubs === 1 ? "" : "s"}
            </Button>
          </div>

          {lastResult && !lastResult.test_only && (
            <div
              className={`rounded-2xl border p-5 ${
                lastResult.status === "sent"
                  ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                  : lastResult.status === "failed"
                    ? "border-rose-200 bg-rose-50 text-rose-900"
                    : "border-border bg-card"
              }`}
            >
              <div className="flex items-start gap-2">
                <CheckCircle2 className="h-4 w-4 mt-0.5 shrink-0" />
                <div className="text-xs">
                  <div className="font-semibold">Last broadcast — {lastResult.status}</div>
                  <div className="mt-1">
                    Sent to {lastResult.recipients_count} ·{" "}
                    {lastResult.delivered} delivered · {lastResult.failed} failed
                  </div>
                  {lastResult.error_summary && (
                    <div className="mt-2 font-mono text-[10px] opacity-80">
                      {lastResult.error_summary}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </aside>
      </div>

      {/* History */}
      <div className="rounded-2xl border border-border bg-card ring-soft">
        <div className="flex items-center gap-2 border-b border-border px-5 py-4">
          <History className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Past broadcasts
          </h3>
        </div>
        {!history || history.length === 0 ? (
          <div className="p-8 text-center text-sm text-muted-foreground">
            No broadcasts sent yet.
          </div>
        ) : (
          <ul className="divide-y divide-border">
            {history.map((b) => (
              <li key={b.id} className="px-5 py-4 flex flex-wrap items-center gap-3">
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium truncate">{b.subject}</div>
                  <div className="mt-0.5 text-xs text-muted-foreground">
                    {b.sender} · {formatDate(b.sent_at ?? b.created_at)}
                  </div>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <span
                    className={`inline-flex rounded-full px-2 py-0.5 font-medium ${
                      b.status === "sent"
                        ? "bg-emerald-100 text-emerald-800"
                        : b.status === "failed"
                          ? "bg-rose-100 text-rose-800"
                          : "bg-secondary text-muted-foreground"
                    }`}
                  >
                    {b.status}
                  </span>
                  <span className="text-muted-foreground">
                    {b.delivered_count}/{b.recipients_count} delivered
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <ConfirmDialog
        open={confirmSend}
        onOpenChange={setConfirmSend}
        title={`Send to ${activeSubs} subscribers?`}
        description="Once sent, the broadcast can't be unsent. Confirm only if the subject and body look final."
        confirmLabel={`Send to ${activeSubs}`}
        onConfirm={() => send({ test: false })}
      />
    </div>
  );
}
