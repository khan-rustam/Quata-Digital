"use client";

import * as React from "react";
import { LogOut, Check, X, RotateCcw } from "lucide-react";
import { FormDialog } from "@/components/admin/form-dialog";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { useApi, useApiAction } from "@/lib/use-api";
import { useToast } from "@/components/ui/toast";

type Exit = {
  exit_type: string;
  exit_date: string | null;
  reason: string | null;
  rehire_eligible: boolean;
  knowledge_transfer: string | null;
  assets_returned: boolean;
  access_revoked: boolean;
  exit_interview_done: boolean;
  final_settlement_done: boolean;
  notes: string | null;
  created_at: string;
} | null;

const TYPE_LABEL: Record<string, string> = {
  resignation: "Resignation", retirement: "Retirement", contract_end: "Contract end",
  dismissal: "Dismissal", redundancy: "Redundancy", death: "Deceased",
};

function fmt(s: string | null): string {
  if (!s) return "—";
  const d = new Date(`${s}T00:00:00`);
  return isNaN(d.getTime()) ? s : d.toLocaleDateString(undefined, { dateStyle: "medium" });
}

function CheckRow({ ok, label }: { ok: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      {ok ? <Check className="h-4 w-4 text-emerald-600" /> : <X className="h-4 w-4 text-muted-foreground" />}
      <span className={ok ? "text-foreground/85" : "text-muted-foreground"}>{label}</span>
    </div>
  );
}

export function EmployeeExitCard({ staffId, onChanged }: { staffId: number; onChanged: () => void }) {
  const { data, loading, refresh } = useApi<Exit>(`/admin/staff/${staffId}/exit`);
  const action = useApiAction();
  const toast = useToast();
  const [open, setOpen] = React.useState(false);
  const [confirmReverse, setConfirmReverse] = React.useState(false);
  const ex = data;

  async function onSubmit(form: FormData) {
    const str = (k: string) => String(form.get(k) || "").trim() || null;
    const payload = {
      exit_type: String(form.get("exit_type") || "resignation"),
      exit_date: str("exit_date"),
      reason: str("reason"),
      rehire_eligible: form.get("rehire_eligible") === "on",
      knowledge_transfer: str("knowledge_transfer"),
      assets_returned: form.get("assets_returned") === "on",
      access_revoked: form.get("access_revoked") === "on",
      exit_interview_done: form.get("exit_interview_done") === "on",
      final_settlement_done: form.get("final_settlement_done") === "on",
      notes: str("notes"),
    };
    try {
      await action(`/admin/staff/${staffId}/exit`, { method: "POST", body: JSON.stringify(payload) });
      toast.success("Employee offboarded");
      setOpen(false);
      refresh();
      onChanged();
    } catch (err) {
      toast.error("Couldn't save", err instanceof Error ? err.message : "Try again.");
    }
  }

  async function reverse() {
    try {
      await action(`/admin/staff/${staffId}/exit`, { method: "DELETE" });
      toast.success("Employee reactivated");
      refresh();
      onChanged();
    } catch (err) {
      toast.error("Couldn't reverse", err instanceof Error ? err.message : "Try again.");
    } finally {
      setConfirmReverse(false);
    }
  }

  return (
    <div className="rounded-2xl border border-border bg-card p-6 ring-soft">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-foreground/90">Offboarding</h2>
        {ex ? (
          <Button size="sm" variant="outline" onClick={() => setConfirmReverse(true)}>
            <RotateCcw className="h-3.5 w-3.5" /> Reactivate
          </Button>
        ) : (
          <Button size="sm" variant="outline" className="text-rose-700" onClick={() => setOpen(true)} disabled={loading}>
            <LogOut className="h-3.5 w-3.5" /> Offboard employee
          </Button>
        )}
      </div>

      {!ex ? (
        <div className="text-sm text-muted-foreground">Employee is active. Offboarding marks them an alumnus.</div>
      ) : (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="danger">{TYPE_LABEL[ex.exit_type] ?? ex.exit_type}</Badge>
            {ex.exit_date && <span className="text-sm text-muted-foreground">{fmt(ex.exit_date)}</span>}
            <Badge variant={ex.rehire_eligible ? "success" : "default"}>
              {ex.rehire_eligible ? "Rehire eligible" : "Not rehire eligible"}
            </Badge>
          </div>
          {ex.reason && <div className="text-sm text-foreground/85 whitespace-pre-line">{ex.reason}</div>}
          <div className="grid gap-1.5 sm:grid-cols-2 rounded-xl border border-border/60 p-3">
            <CheckRow ok={ex.assets_returned} label="Assets returned" />
            <CheckRow ok={ex.access_revoked} label="Access revoked" />
            <CheckRow ok={ex.exit_interview_done} label="Exit interview done" />
            <CheckRow ok={ex.final_settlement_done} label="Final settlement done" />
          </div>
          {ex.knowledge_transfer && (
            <div className="text-sm"><span className="text-[10px] uppercase tracking-wider text-muted-foreground">Knowledge transfer</span><div className="whitespace-pre-line text-foreground/85">{ex.knowledge_transfer}</div></div>
          )}
          {ex.notes && <div className="text-sm text-foreground/85 whitespace-pre-line">{ex.notes}</div>}
        </div>
      )}

      <FormDialog open={open} onOpenChange={setOpen} title="Offboard employee" submitLabel="Offboard" onSubmit={onSubmit}>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="grid gap-1.5">
            <Label htmlFor="exit_type">Exit type *</Label>
            <Select id="exit_type" name="exit_type" defaultValue="resignation">
              {Object.entries(TYPE_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="exit_date">Exit date</Label>
            <Input id="exit_date" name="exit_date" type="date" />
          </div>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="reason">Reason</Label>
          <Textarea id="reason" name="reason" rows={2} />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="knowledge_transfer">Knowledge transfer / handover</Label>
          <Textarea id="knowledge_transfer" name="knowledge_transfer" rows={2} />
        </div>
        <div className="grid gap-2 rounded-xl border border-border p-3 sm:grid-cols-2">
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" name="assets_returned" className="h-4 w-4 rounded border-border" /> Assets returned</label>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" name="access_revoked" className="h-4 w-4 rounded border-border" /> Access revoked</label>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" name="exit_interview_done" className="h-4 w-4 rounded border-border" /> Exit interview done</label>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" name="final_settlement_done" className="h-4 w-4 rounded border-border" /> Final settlement done</label>
          <label className="flex items-center gap-2 text-sm sm:col-span-2"><input type="checkbox" name="rehire_eligible" defaultChecked className="h-4 w-4 rounded border-border" /> Eligible for rehire</label>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="notes">Notes</Label>
          <Textarea id="notes" name="notes" rows={2} />
        </div>
      </FormDialog>

      <ConfirmDialog
        open={confirmReverse}
        onOpenChange={setConfirmReverse}
        title="Reactivate this employee?"
        description="This removes the exit record and returns them to active status."
        confirmLabel="Reactivate"
        onConfirm={reverse}
      />
    </div>
  );
}
