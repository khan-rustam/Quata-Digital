"use client";

import * as React from "react";
import { ExternalLink, Loader2, Mail, Phone } from "lucide-react";
import { SlideOver, SlideOverContent } from "@/components/admin/slide-over";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useApi, useApiAction } from "@/lib/use-api";
import { useToast } from "@/components/ui/toast";

type AppDetail = {
  id: number;
  full_name: string;
  email: string;
  phone: string | null;
  resume_url: string;
  cover_letter: string | null;
  status: "new" | "shortlisted" | "interviewed" | "rejected" | "hired";
  job_title: string | null;
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

  async function setStatus(status: AppDetail["status"]) {
    if (!applicationId) return;
    try {
      await action(`/admin/applications/${applicationId}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      toast.success(`Marked ${status}`);
      onChanged();
    } catch (err) {
      toast.error("Couldn't update", err instanceof Error ? err.message : "Try again.");
    }
  }

  return (
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
                  <Button size="sm" variant="ghost" onClick={() => setStatus("shortlisted")}>Shortlist</Button>
                  <Button size="sm" variant="ghost" onClick={() => setStatus("interviewed")}>Interviewed</Button>
                  <Button size="sm" onClick={() => setStatus("hired")}>Hire</Button>
                  <Button size="sm" variant="ghost" className="text-rose-700" onClick={() => setStatus("rejected")}>
                    Reject
                  </Button>
                </div>
              </div>
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

            {/* Resume */}
            <div>
              <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Resume</div>
              <a
                href={data.resume_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 rounded-xl border border-border bg-card px-4 py-3 text-sm hover:bg-surface-soft transition"
              >
                <ExternalLink className="h-4 w-4 text-primary" />
                Open resume
                <code className="text-[10px] text-muted-foreground truncate max-w-[280px]">{data.resume_url}</code>
              </a>
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
  );
}
