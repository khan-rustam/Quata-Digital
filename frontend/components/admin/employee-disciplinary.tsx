"use client";

import * as React from "react";
import { Plus, Trash2, ShieldAlert, Lock } from "lucide-react";
import { FormDialog } from "@/components/admin/form-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { useApi, useApiAction } from "@/lib/use-api";
import { useToast } from "@/components/ui/toast";

type Action = {
  id: number;
  action_type: string;
  action_date: string | null;
  summary: string;
  outcome: string | null;
  status: string;
  issued_by: string | null;
  created_at: string;
};

const TYPE_LABEL: Record<string, string> = {
  verbal_warning: "Verbal warning",
  written_warning: "Written warning",
  suspension: "Suspension",
  investigation: "Investigation",
  final_warning: "Final warning",
  other: "Other",
};
const statusVariant: Record<string, "warn" | "success" | "default"> = {
  open: "warn", resolved: "success", appealed: "default",
};

function fmt(s: string | null): string {
  if (!s) return "—";
  const d = new Date(`${s}T00:00:00`);
  return isNaN(d.getTime()) ? s : d.toLocaleDateString(undefined, { dateStyle: "medium" });
}

export function EmployeeDisciplinary({ staffId }: { staffId: number }) {
  const items = useApi<Action[]>(`/admin/staff/${staffId}/disciplinary`);
  const action = useApiAction();
  const toast = useToast();
  const [open, setOpen] = React.useState(false);

  async function onSubmit(form: FormData) {
    const str = (k: string) => String(form.get(k) || "").trim() || null;
    const payload = {
      action_type: String(form.get("action_type") || "other"),
      action_date: str("action_date"),
      summary: String(form.get("summary")),
      outcome: str("outcome"),
      status: String(form.get("status") || "open"),
    };
    try {
      await action(`/admin/staff/${staffId}/disciplinary`, { method: "POST", body: JSON.stringify(payload) });
      toast.success("Record added");
      setOpen(false);
      items.refresh();
    } catch (err) {
      toast.error("Couldn't save", err instanceof Error ? err.message : "Try again.");
    }
  }

  async function del(id: number) {
    try {
      await action(`/admin/staff/${staffId}/disciplinary/${id}`, { method: "DELETE" });
      items.refresh();
    } catch (err) {
      toast.error("Couldn't delete", err instanceof Error ? err.message : "Try again.");
    }
  }

  const rows = items.data ?? [];

  return (
    <div className="rounded-2xl border border-border bg-card p-6 ring-soft">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-foreground/90">Disciplinary</h2>
          <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider text-muted-foreground">
            <Lock className="h-3 w-3" /> Confidential
          </span>
        </div>
        <Button size="sm" variant="outline" onClick={() => setOpen(true)}>
          <Plus className="h-3.5 w-3.5" /> Add record
        </Button>
      </div>
      {rows.length === 0 ? (
        <div className="text-sm text-muted-foreground">No disciplinary records.</div>
      ) : (
        <div className="space-y-2">
          {rows.map((d) => (
            <div key={d.id} className="flex items-start gap-3 rounded-xl border border-border p-3">
              <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium">{TYPE_LABEL[d.action_type] ?? d.action_type}</span>
                  <Badge variant={statusVariant[d.status] ?? "default"} className="capitalize">{d.status}</Badge>
                  {d.action_date && <span className="text-[11px] text-muted-foreground">{fmt(d.action_date)}</span>}
                </div>
                <div className="mt-1 whitespace-pre-line text-sm text-foreground/85">{d.summary}</div>
                {d.outcome && <div className="mt-1 text-sm text-foreground/85"><span className="text-[10px] uppercase tracking-wider text-muted-foreground">Outcome</span><div className="whitespace-pre-line">{d.outcome}</div></div>}
                <div className="mt-1 text-[11px] text-muted-foreground">{d.issued_by ?? "—"} · {new Date(d.created_at).toLocaleDateString()}</div>
              </div>
              <button type="button" onClick={() => del(d.id)} className="text-muted-foreground hover:text-rose-700" aria-label="Delete record">
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      <FormDialog open={open} onOpenChange={setOpen} title="Add disciplinary record" submitLabel="Save" onSubmit={onSubmit}>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="grid gap-1.5">
            <Label htmlFor="action_type">Type *</Label>
            <Select id="action_type" name="action_type" defaultValue="verbal_warning">
              {Object.entries(TYPE_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="action_date">Date</Label>
            <Input id="action_date" name="action_date" type="date" />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="status">Status</Label>
            <Select id="status" name="status" defaultValue="open">
              <option value="open">Open</option>
              <option value="resolved">Resolved</option>
              <option value="appealed">Appealed</option>
            </Select>
          </div>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="summary">Summary *</Label>
          <Textarea id="summary" name="summary" rows={3} required placeholder="What happened, and the action taken." />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="outcome">Outcome / resolution</Label>
          <Textarea id="outcome" name="outcome" rows={2} />
        </div>
      </FormDialog>
    </div>
  );
}
