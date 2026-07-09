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
import { Badge } from "@/components/ui/badge";
import { TableSkeleton } from "@/components/ui/skeleton";
import { useApi, useApiAction } from "@/lib/use-api";
import { useToast } from "@/components/ui/toast";

type BusinessUnit = {
  id: number;
  slug: string;
  name: string;
  description: string | null;
  is_active: boolean;
  sort_order: number;
  department_count: number;
};

export default function BusinessUnitsPage() {
  const { data, loading, refresh } = useApi<BusinessUnit[]>("/admin/business-units");
  const action = useApiAction();
  const toast = useToast();
  const [open, setOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<BusinessUnit | null>(null);
  const [deleting, setDeleting] = React.useState<BusinessUnit | null>(null);

  async function onSubmit(form: FormData) {
    const payload = {
      slug: String(form.get("slug")),
      name: String(form.get("name")),
      description: String(form.get("description") || "") || null,
      is_active: form.get("is_active") === "on",
      sort_order: Number(form.get("sort_order") || 0),
    };
    try {
      if (editing) {
        await action(`/admin/business-units/${editing.id}`, { method: "PUT", body: JSON.stringify(payload) });
        toast.success("Business unit updated", payload.name);
      } else {
        await action("/admin/business-units", { method: "POST", body: JSON.stringify(payload) });
        toast.success("Business unit created", payload.name);
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
      await action(`/admin/business-units/${deleting.id}`, { method: "DELETE" });
      toast.success("Business unit removed", deleting.name);
      refresh();
    } catch (err) {
      toast.error("Couldn't delete", err instanceof Error ? err.message : "Try again.");
    } finally {
      setDeleting(null);
    }
  }

  const columns: Column<BusinessUnit>[] = [
    { key: "name", header: "Business unit", cell: (r) => <span className="font-medium">{r.name}</span> },
    { key: "slug", header: "Slug", cell: (r) => <code className="text-xs">{r.slug}</code> },
    { key: "depts", header: "Departments", cell: (r) => r.department_count },
    {
      key: "active",
      header: "Status",
      cell: (r) => (
        <Badge variant={r.is_active ? "success" : "outline"}>{r.is_active ? "Active" : "Inactive"}</Badge>
      ),
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
      title="Business units"
      description="QUATA business units (distinct from products): Corporate Services, QuataPay, QuataTrade, QuataFood, Abaqwa and beyond."
      requirePermission="staff:manage"
      actions={
        <Button onClick={() => { setEditing(null); setOpen(true); }}>
          <Plus className="h-4 w-4" /> New business unit
        </Button>
      }
    >
      {loading ? (
        <TableSkeleton rows={5} cols={5} />
      ) : (
        <DataTable columns={columns} rows={data ?? []} loading={false} empty="No business units yet." />
      )}

      <FormDialog
        open={open}
        onOpenChange={setOpen}
        title={editing ? `Edit ${editing.name}` : "New business unit"}
        onSubmit={onSubmit}
        submitLabel={editing ? "Save changes" : "Create"}
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="slug">Slug *</Label>
            <Input id="slug" name="slug" required defaultValue={editing?.slug} placeholder="quatapay" />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="name">Name *</Label>
            <Input id="name" name="name" required defaultValue={editing?.name} placeholder="QuataPay" />
          </div>
        </div>
        <div className="grid gap-2">
          <Label htmlFor="description">Description</Label>
          <Input id="description" name="description" defaultValue={editing?.description ?? ""} placeholder="What this business unit does (optional)" />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="sort_order">Sort order</Label>
            <Input id="sort_order" name="sort_order" type="number" defaultValue={editing?.sort_order ?? 0} />
          </div>
          <label className="flex items-center gap-2 text-sm mt-7">
            <input type="checkbox" name="is_active" defaultChecked={editing?.is_active ?? true} className="h-4 w-4 rounded border-border" />
            Active
          </label>
        </div>
      </FormDialog>

      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(v) => !v && setDeleting(null)}
        title={`Delete ${deleting?.name ?? "business unit"}?`}
        description="Departments will be detached from this unit but not deleted."
        confirmLabel="Delete"
        destructive
        onConfirm={onDelete}
      />
    </PageShell>
  );
}
