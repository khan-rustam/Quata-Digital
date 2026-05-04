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
import { TableSkeleton } from "@/components/ui/skeleton";
import { useApi, useApiAction } from "@/lib/use-api";
import { useToast } from "@/components/ui/toast";

type Department = {
  id: number;
  name: string;
  slug: string;
  head_name: string | null;
  staff_count: number;
};

export default function DepartmentsPage() {
  const { data, loading, refresh } = useApi<Department[]>("/admin/departments");
  const action = useApiAction();
  const toast = useToast();
  const [open, setOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<Department | null>(null);
  const [deleting, setDeleting] = React.useState<Department | null>(null);

  async function onSubmit(form: FormData) {
    const payload = {
      slug: String(form.get("slug")),
      name: String(form.get("name")),
      description: String(form.get("description") || "") || null,
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
    { key: "slug", header: "Slug", cell: (r) => <code className="text-xs">{r.slug}</code> },
    { key: "head", header: "Head", cell: (r) => r.head_name ?? "—" },
    { key: "count", header: "Headcount", cell: (r) => r.staff_count },
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
            <Input id="slug" name="slug" required defaultValue={editing?.slug} />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="name">Name *</Label>
            <Input id="name" name="name" required defaultValue={editing?.name} />
          </div>
        </div>
        <div className="grid gap-2">
          <Label htmlFor="description">Description</Label>
          <Input id="description" name="description" />
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
