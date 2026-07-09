"use client";

import * as React from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { PageShell } from "@/components/admin/page-shell";
import { DataTable, type Column } from "@/components/admin/data-table";
import { FormDialog } from "@/components/admin/form-dialog";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { TableSkeleton } from "@/components/ui/skeleton";
import { useApi, useApiAction } from "@/lib/use-api";
import { useToast } from "@/components/ui/toast";

type Department = {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  head_name: string | null;
  head_id: number | null;
  assistant_head_id: number | null;
  staff_count: number;
  business_unit_id: number | null;
  business_unit_name: string | null;
  objectives: string | null;
  kpis: string | null;
  budget: number | null;
  max_headcount: number | null;
  office_location: string | null;
};

type BusinessUnitLite = { id: number; name: string };
type StaffLite = { id: number; full_name: string };

export default function DepartmentsPage() {
  const { data, loading, refresh } = useApi<Department[]>("/admin/departments");
  const businessUnits = useApi<BusinessUnitLite[]>("/admin/business-units");
  const staff = useApi<StaffLite[]>("/admin/staff");
  const action = useApiAction();
  const toast = useToast();
  const [open, setOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<Department | null>(null);
  const [deleting, setDeleting] = React.useState<Department | null>(null);

  async function onSubmit(form: FormData) {
    const num = (k: string) => {
      const v = String(form.get(k) || "").trim();
      return v ? Number(v) : null;
    };
    const payload = {
      slug: String(form.get("slug")),
      name: String(form.get("name")),
      description: String(form.get("description") || "") || null,
      business_unit_id: num("business_unit_id"),
      head_id: num("head_id"),
      assistant_head_id: num("assistant_head_id"),
      office_location: String(form.get("office_location") || "").trim() || null,
      max_headcount: num("max_headcount"),
      budget: num("budget"),
      objectives: String(form.get("objectives") || "").trim() || null,
      kpis: String(form.get("kpis") || "").trim() || null,
    };
    try {
      if (editing) {
        await action(`/admin/departments/${editing.id}`, { method: "PUT", body: JSON.stringify(payload) });
        toast.success("Department updated", payload.name);
      } else {
        await action("/admin/departments", { method: "POST", body: JSON.stringify(payload) });
        toast.success("Department created", payload.name);
      }
      setOpen(false);
      refresh();
    } catch (err) {
      toast.error("Couldn't save", err instanceof Error ? err.message : "Try again.");
    }
  }

  async function onDelete() {
    if (!deleting) return;
    try {
      await action(`/admin/departments/${deleting.id}`, { method: "DELETE" });
      toast.success("Department removed", deleting.name);
      refresh();
    } catch (err) {
      toast.error("Couldn't delete", err instanceof Error ? err.message : "Try again.");
    } finally {
      setDeleting(null);
    }
  }

  const columns: Column<Department>[] = [
    { key: "name", header: "Department", cell: (r) => <span className="font-medium">{r.name}</span> },
    { key: "bu", header: "Business unit", cell: (r) => r.business_unit_name ?? "—" },
    { key: "head", header: "Head", cell: (r) => r.head_name ?? "—" },
    {
      key: "count",
      header: "Headcount",
      cell: (r) => (r.max_headcount ? `${r.staff_count} / ${r.max_headcount}` : r.staff_count),
    },
    {
      key: "actions",
      header: "",
      className: "w-32 text-right",
      cell: (r) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="ghost" onClick={() => { setEditing(r); setOpen(true); }}>
            <Pencil className="h-3.5 w-3.5" />
          </Button>
          <Button size="sm" variant="ghost" className="text-rose-700" onClick={() => setDeleting(r)}>
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      ),
    },
  ];

  return (
    <PageShell
      title="Departments"
      description="Engineering, Finance, Operations, Marketing, Support, Legal, HR, Field Operations."
      requirePermission="staff:manage"
      actions={
        <Button onClick={() => { setEditing(null); setOpen(true); }}>
          <Plus className="h-4 w-4" /> New department
        </Button>
      }
    >
      {loading ? (
        <TableSkeleton rows={5} cols={5} />
      ) : (
        <DataTable columns={columns} rows={data ?? []} loading={false} />
      )}

      <FormDialog
        open={open}
        onOpenChange={setOpen}
        title={editing ? `Edit ${editing.name}` : "New department"}
        onSubmit={onSubmit}
        submitLabel={editing ? "Save changes" : "Create"}
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="slug">Slug *</Label>
            <Input id="slug" name="slug" required defaultValue={editing?.slug} placeholder="engineering" />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="name">Name *</Label>
            <Input id="name" name="name" required defaultValue={editing?.name} placeholder="Engineering" />
          </div>
        </div>
        <div className="grid gap-2">
          <Label htmlFor="description">Description</Label>
          <Input id="description" name="description" defaultValue={editing?.description ?? ""} placeholder="What this department does (optional)" />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="business_unit_id">Business unit</Label>
            <Select id="business_unit_id" name="business_unit_id" defaultValue={editing?.business_unit_id ?? ""}>
              <option value="">— None —</option>
              {(businessUnits.data ?? []).map((b) => (
                <option key={b.id} value={b.id}>{b.name}</option>
              ))}
            </Select>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="office_location">Office location</Label>
            <Input id="office_location" name="office_location" defaultValue={editing?.office_location ?? ""} placeholder="Bamenda, Cameroon" />
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="head_id">Department head</Label>
            <Select id="head_id" name="head_id" defaultValue={editing?.head_id ?? ""}>
              <option value="">— Unassigned —</option>
              {(staff.data ?? []).map((s) => (
                <option key={s.id} value={s.id}>{s.full_name}</option>
              ))}
            </Select>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="assistant_head_id">Assistant head</Label>
            <Select id="assistant_head_id" name="assistant_head_id" defaultValue={editing?.assistant_head_id ?? ""}>
              <option value="">— Unassigned —</option>
              {(staff.data ?? []).map((s) => (
                <option key={s.id} value={s.id}>{s.full_name}</option>
              ))}
            </Select>
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="max_headcount">Max headcount</Label>
            <Input id="max_headcount" name="max_headcount" type="number" defaultValue={editing?.max_headcount ?? ""} placeholder="e.g. 12" />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="budget">Annual budget (XAF)</Label>
            <Input id="budget" name="budget" type="number" defaultValue={editing?.budget ?? ""} placeholder="e.g. 25000000" />
          </div>
        </div>
        <div className="grid gap-2">
          <Label htmlFor="objectives">Objectives</Label>
          <Textarea id="objectives" name="objectives" rows={2} defaultValue={editing?.objectives ?? ""} placeholder="What this department is accountable for." />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="kpis">KPIs (one per line)</Label>
          <Textarea id="kpis" name="kpis" rows={3} defaultValue={editing?.kpis ?? ""} placeholder="Key metrics this department is measured on." />
        </div>
      </FormDialog>

      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(v) => !v && setDeleting(null)}
        title={`Delete ${deleting?.name ?? "department"}?`}
        description="Members will be detached from this department but not deleted."
        confirmLabel="Delete"
        destructive
        onConfirm={onDelete}
      />
    </PageShell>
  );
}
