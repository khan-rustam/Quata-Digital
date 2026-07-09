"use client";

import * as React from "react";
import { Plus, Trash2, GraduationCap } from "lucide-react";
import { FormDialog } from "@/components/admin/form-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { useApi, useApiAction } from "@/lib/use-api";
import { useToast } from "@/components/ui/toast";

type Training = {
  id: number;
  title: string;
  provider: string | null;
  training_type: string | null;
  status: string;
  completed_on: string | null;
  expires_on: string | null;
  notes: string | null;
};

const statusVariant: Record<string, "success" | "warn" | "default"> = {
  completed: "success",
  in_progress: "warn",
  planned: "default",
};

function fmt(s: string | null): string {
  if (!s) return "—";
  const d = new Date(`${s}T00:00:00`);
  return isNaN(d.getTime()) ? s : d.toLocaleDateString(undefined, { dateStyle: "medium" });
}

export function EmployeeTraining({ staffId }: { staffId: number }) {
  const training = useApi<Training[]>(`/admin/staff/${staffId}/training`);
  const action = useApiAction();
  const toast = useToast();
  const [open, setOpen] = React.useState(false);

  async function onSubmit(form: FormData) {
    const str = (k: string) => String(form.get(k) || "").trim() || null;
    const payload = {
      title: String(form.get("title")),
      provider: str("provider"),
      training_type: str("training_type"),
      status: String(form.get("status") || "completed"),
      completed_on: str("completed_on"),
      expires_on: str("expires_on"),
      notes: str("notes"),
    };
    try {
      await action(`/admin/staff/${staffId}/training`, { method: "POST", body: JSON.stringify(payload) });
      toast.success("Training added");
      setOpen(false);
      training.refresh();
    } catch (err) {
      toast.error("Couldn't save", err instanceof Error ? err.message : "Try again.");
    }
  }

  async function del(id: number) {
    try {
      await action(`/admin/staff/${staffId}/training/${id}`, { method: "DELETE" });
      training.refresh();
    } catch (err) {
      toast.error("Couldn't delete", err instanceof Error ? err.message : "Try again.");
    }
  }

  const rows = training.data ?? [];

  return (
    <div className="rounded-2xl border border-border bg-card p-6 ring-soft">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-foreground/90">Training records</h2>
        <Button size="sm" variant="outline" onClick={() => setOpen(true)}>
          <Plus className="h-3.5 w-3.5" /> Add training
        </Button>
      </div>
      {rows.length === 0 ? (
        <div className="text-sm text-muted-foreground">No training records yet.</div>
      ) : (
        <div className="space-y-2">
          {rows.map((t) => (
            <div key={t.id} className="flex items-start gap-3 rounded-xl border border-border p-3">
              <GraduationCap className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium">{t.title}</span>
                  <Badge variant={statusVariant[t.status] ?? "default"} className="capitalize">{t.status.replace("_", " ")}</Badge>
                  {t.training_type && <Badge variant="outline" className="capitalize">{t.training_type}</Badge>}
                </div>
                <div className="text-[11px] text-muted-foreground">
                  {t.provider ?? "—"}
                  {t.completed_on ? ` · completed ${fmt(t.completed_on)}` : ""}
                  {t.expires_on ? ` · expires ${fmt(t.expires_on)}` : ""}
                </div>
                {t.notes && <div className="mt-1 whitespace-pre-line text-sm text-foreground/85">{t.notes}</div>}
              </div>
              <button type="button" onClick={() => del(t.id)} className="text-muted-foreground hover:text-rose-700" aria-label="Delete training">
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      <FormDialog open={open} onOpenChange={setOpen} title="Add training record" submitLabel="Save" onSubmit={onSubmit}>
        <div className="grid gap-1.5">
          <Label htmlFor="title">Course / training *</Label>
          <Input id="title" name="title" required placeholder="AML & compliance basics" />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="grid gap-1.5">
            <Label htmlFor="provider">Provider</Label>
            <Input id="provider" name="provider" placeholder="Internal / Coursera / …" />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="training_type">Type</Label>
            <Select id="training_type" name="training_type" defaultValue="">
              <option value="">—</option>
              <option value="internal">Internal</option>
              <option value="external">External</option>
              <option value="compliance">Compliance</option>
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="status">Status</Label>
            <Select id="status" name="status" defaultValue="completed">
              <option value="completed">Completed</option>
              <option value="in_progress">In progress</option>
              <option value="planned">Planned</option>
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="completed_on">Completed on</Label>
            <Input id="completed_on" name="completed_on" type="date" />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="expires_on">Expires on</Label>
            <Input id="expires_on" name="expires_on" type="date" />
          </div>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="notes">Notes</Label>
          <Textarea id="notes" name="notes" rows={2} />
        </div>
      </FormDialog>
    </div>
  );
}
