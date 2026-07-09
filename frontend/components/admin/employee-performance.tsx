"use client";

import * as React from "react";
import { Plus, Trash2 } from "lucide-react";
import { FormDialog } from "@/components/admin/form-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { useApi, useApiAction } from "@/lib/use-api";
import { useToast } from "@/components/ui/toast";

type Review = {
  id: number;
  period: string;
  rating: number | null;
  strengths: string | null;
  improvements: string | null;
  goals: string | null;
  status: string;
  reviewer_name: string | null;
  created_at: string;
};

export function EmployeePerformance({ staffId }: { staffId: number }) {
  const reviews = useApi<Review[]>(`/admin/staff/${staffId}/reviews`);
  const action = useApiAction();
  const toast = useToast();
  const [open, setOpen] = React.useState(false);

  async function onSubmit(form: FormData) {
    const payload = {
      period: String(form.get("period")),
      rating: form.get("rating") ? Number(form.get("rating")) : null,
      strengths: String(form.get("strengths") || "").trim() || null,
      improvements: String(form.get("improvements") || "").trim() || null,
      goals: String(form.get("goals") || "").trim() || null,
    };
    try {
      await action(`/admin/staff/${staffId}/reviews`, { method: "POST", body: JSON.stringify(payload) });
      toast.success("Review added");
      setOpen(false);
      reviews.refresh();
    } catch (err) {
      toast.error("Couldn't save", err instanceof Error ? err.message : "Try again.");
    }
  }

  async function del(id: number) {
    try {
      await action(`/admin/staff/${staffId}/reviews/${id}`, { method: "DELETE" });
      reviews.refresh();
    } catch (err) {
      toast.error("Couldn't delete", err instanceof Error ? err.message : "Try again.");
    }
  }

  const rows = reviews.data ?? [];

  return (
    <div className="rounded-2xl border border-border bg-card p-6 ring-soft">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-foreground/90">Performance reviews</h2>
        <Button size="sm" variant="outline" onClick={() => setOpen(true)}>
          <Plus className="h-3.5 w-3.5" /> Add review
        </Button>
      </div>
      {rows.length === 0 ? (
        <div className="text-sm text-muted-foreground">No reviews yet.</div>
      ) : (
        <div className="space-y-3">
          {rows.map((r) => (
            <div key={r.id} className="rounded-xl border border-border p-3">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">{r.period}</span>
                  {r.rating ? <Badge variant="brand">{r.rating}/5</Badge> : null}
                </div>
                <button type="button" onClick={() => del(r.id)} className="text-muted-foreground hover:text-rose-700" aria-label="Delete review">
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
              {r.strengths && (
                <div className="mt-1.5 text-sm">
                  <span className="text-[10px] uppercase tracking-wider text-emerald-700">Strengths</span>
                  <div className="whitespace-pre-line text-foreground/85">{r.strengths}</div>
                </div>
              )}
              {r.improvements && (
                <div className="mt-1.5 text-sm">
                  <span className="text-[10px] uppercase tracking-wider text-amber-700">To improve</span>
                  <div className="whitespace-pre-line text-foreground/85">{r.improvements}</div>
                </div>
              )}
              {r.goals && (
                <div className="mt-1.5 text-sm">
                  <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Goals</span>
                  <div className="whitespace-pre-line text-foreground/85">{r.goals}</div>
                </div>
              )}
              <div className="mt-1.5 text-[11px] text-muted-foreground">
                {r.reviewer_name ?? "—"} · {new Date(r.created_at).toLocaleDateString()}
              </div>
            </div>
          ))}
        </div>
      )}

      <FormDialog open={open} onOpenChange={setOpen} title="Add performance review" submitLabel="Save review" onSubmit={onSubmit}>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="grid gap-1.5">
            <Label htmlFor="period">Period *</Label>
            <Input id="period" name="period" required placeholder="2026 H1" />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="rating">Rating</Label>
            <Select id="rating" name="rating" defaultValue="">
              <option value="">—</option>
              <option value="5">5 — Outstanding</option>
              <option value="4">4 — Exceeds expectations</option>
              <option value="3">3 — Meets expectations</option>
              <option value="2">2 — Below expectations</option>
              <option value="1">1 — Needs improvement</option>
            </Select>
          </div>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="strengths">Strengths</Label>
          <Textarea id="strengths" name="strengths" rows={2} />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="improvements">Areas to improve</Label>
          <Textarea id="improvements" name="improvements" rows={2} />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="goals">Goals for next period</Label>
          <Textarea id="goals" name="goals" rows={2} />
        </div>
      </FormDialog>
    </div>
  );
}
