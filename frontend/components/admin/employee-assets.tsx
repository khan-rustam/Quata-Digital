"use client";

import * as React from "react";
import { Plus, Trash2, Package } from "lucide-react";
import { FormDialog } from "@/components/admin/form-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { useApi, useApiAction } from "@/lib/use-api";
import { useToast } from "@/components/ui/toast";

type Asset = {
  id: number;
  asset_type: string;
  name: string;
  serial: string | null;
  condition: string | null;
  status: string;
  assigned_on: string | null;
  returned_on: string | null;
  notes: string | null;
};

const TYPE_LABEL: Record<string, string> = {
  laptop: "Laptop", desktop: "Desktop", phone: "Phone", sim: "SIM card",
  vehicle: "Vehicle", access_card: "Access card", keys: "Keys", uniform: "Uniform", other: "Other",
};
const statusVariant: Record<string, "success" | "warn" | "danger" | "default"> = {
  assigned: "success", returned: "default", repair: "warn", lost: "danger",
};

function fmt(s: string | null): string {
  if (!s) return "—";
  const d = new Date(`${s}T00:00:00`);
  return isNaN(d.getTime()) ? s : d.toLocaleDateString(undefined, { dateStyle: "medium" });
}

export function EmployeeAssets({ staffId }: { staffId: number }) {
  const assets = useApi<Asset[]>(`/admin/staff/${staffId}/assets`);
  const action = useApiAction();
  const toast = useToast();
  const [open, setOpen] = React.useState(false);

  async function onSubmit(form: FormData) {
    const str = (k: string) => String(form.get(k) || "").trim() || null;
    const payload = {
      asset_type: String(form.get("asset_type") || "other"),
      name: String(form.get("name")),
      serial: str("serial"),
      condition: str("condition"),
      status: String(form.get("status") || "assigned"),
      assigned_on: str("assigned_on"),
      returned_on: str("returned_on"),
      notes: str("notes"),
    };
    try {
      await action(`/admin/staff/${staffId}/assets`, { method: "POST", body: JSON.stringify(payload) });
      toast.success("Asset assigned");
      setOpen(false);
      assets.refresh();
    } catch (err) {
      toast.error("Couldn't save", err instanceof Error ? err.message : "Try again.");
    }
  }

  async function del(id: number) {
    try {
      await action(`/admin/staff/${staffId}/assets/${id}`, { method: "DELETE" });
      assets.refresh();
    } catch (err) {
      toast.error("Couldn't delete", err instanceof Error ? err.message : "Try again.");
    }
  }

  const rows = assets.data ?? [];

  return (
    <div className="rounded-2xl border border-border bg-card p-6 ring-soft">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-foreground/90">Assigned assets</h2>
        <Button size="sm" variant="outline" onClick={() => setOpen(true)}>
          <Plus className="h-3.5 w-3.5" /> Assign asset
        </Button>
      </div>
      {rows.length === 0 ? (
        <div className="text-sm text-muted-foreground">No assets assigned.</div>
      ) : (
        <div className="space-y-2">
          {rows.map((a) => (
            <div key={a.id} className="flex items-start gap-3 rounded-xl border border-border p-3">
              <Package className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium">{a.name}</span>
                  <Badge variant="outline">{TYPE_LABEL[a.asset_type] ?? a.asset_type}</Badge>
                  <Badge variant={statusVariant[a.status] ?? "default"} className="capitalize">{a.status}</Badge>
                </div>
                <div className="text-[11px] text-muted-foreground">
                  {a.serial ? `SN ${a.serial}` : "—"}
                  {a.condition ? ` · ${a.condition}` : ""}
                  {a.assigned_on ? ` · assigned ${fmt(a.assigned_on)}` : ""}
                  {a.returned_on ? ` · returned ${fmt(a.returned_on)}` : ""}
                </div>
                {a.notes && <div className="mt-1 whitespace-pre-line text-sm text-foreground/85">{a.notes}</div>}
              </div>
              <button type="button" onClick={() => del(a.id)} className="text-muted-foreground hover:text-rose-700" aria-label="Remove asset">
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      <FormDialog open={open} onOpenChange={setOpen} title="Assign an asset" submitLabel="Assign" onSubmit={onSubmit}>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="grid gap-1.5">
            <Label htmlFor="asset_type">Type *</Label>
            <Select id="asset_type" name="asset_type" defaultValue="laptop">
              {Object.entries(TYPE_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="name">Name / label *</Label>
            <Input id="name" name="name" required placeholder="Dell Latitude 5440" />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="serial">Serial / tag</Label>
            <Input id="serial" name="serial" />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="condition">Condition</Label>
            <Select id="condition" name="condition" defaultValue="">
              <option value="">—</option>
              <option value="new">New</option>
              <option value="good">Good</option>
              <option value="fair">Fair</option>
              <option value="poor">Poor</option>
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="status">Status</Label>
            <Select id="status" name="status" defaultValue="assigned">
              <option value="assigned">Assigned</option>
              <option value="returned">Returned</option>
              <option value="repair">In repair</option>
              <option value="lost">Lost</option>
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="assigned_on">Assigned on</Label>
            <Input id="assigned_on" name="assigned_on" type="date" />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="returned_on">Returned on</Label>
            <Input id="returned_on" name="returned_on" type="date" />
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
