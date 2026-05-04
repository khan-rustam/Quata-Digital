"use client";

import * as React from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { PageShell } from "@/components/admin/page-shell";
import { DataTable, type Column } from "@/components/admin/data-table";
import { FormDialog } from "@/components/admin/form-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select } from "@/components/ui/select";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { TableSkeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useApi, useApiAction } from "@/lib/use-api";

type Product = {
  id: number;
  slug: string;
  name: string;
  category: string;
  status: "live" | "beta" | "coming_soon";
  tagline: string;
  description: string;
  is_published: boolean;
};

const statusMap = {
  live: { label: "Live", variant: "live" as const },
  beta: { label: "Beta", variant: "beta" as const },
  coming_soon: { label: "Coming soon", variant: "soon" as const },
};

export default function ProductsAdminPage() {
  const { data, loading, refresh } = useApi<Product[]>("/admin/products");
  const action = useApiAction();
  const toast = useToast();

  const [open, setOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<Product | null>(null);
  const [deleting, setDeleting] = React.useState<Product | null>(null);

  function openCreate() {
    setEditing(null);
    setOpen(true);
  }
  function openEdit(p: Product) {
    setEditing(p);
    setOpen(true);
  }

  async function onSubmit(form: FormData) {
    const payload = {
      slug: String(form.get("slug")),
      name: String(form.get("name")),
      tagline: String(form.get("tagline")),
      description: String(form.get("description")),
      category: String(form.get("category")),
      status: String(form.get("status")),
      is_published: form.get("is_published") === "on",
    };
    try {
      if (editing) {
        await action(`/admin/products/${editing.id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        toast.success("Product updated", payload.name);
      } else {
        await action("/admin/products", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        toast.success("Product created", payload.name);
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
      await action(`/admin/products/${deleting.id}`, { method: "DELETE" });
      toast.success("Product removed", deleting.name);
      refresh();
    } catch (err) {
      toast.error("Couldn't delete", err instanceof Error ? err.message : "Try again.");
    } finally {
      setDeleting(null);
    }
  }

  const columns: Column<Product>[] = [
    {
      key: "name",
      header: "Product",
      cell: (r) => (
        <div>
          <div className="font-medium">{r.name}</div>
          <div className="text-xs text-muted-foreground">{r.tagline}</div>
        </div>
      ),
    },
    { key: "category", header: "Category", cell: (r) => r.category },
    {
      key: "status",
      header: "Status",
      cell: (r) => <Badge variant={statusMap[r.status].variant}>{statusMap[r.status].label}</Badge>,
    },
    {
      key: "published",
      header: "Public",
      cell: (r) => (
        <Badge variant={r.is_published ? "success" : "outline"}>
          {r.is_published ? "Published" : "Draft"}
        </Badge>
      ),
    },
    {
      key: "actions",
      header: "",
      className: "w-32",
      cell: (r) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="ghost" onClick={() => openEdit(r)}>
            <Pencil className="h-3.5 w-3.5" /> Edit
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
      title="Products"
      description="Manage descriptions, status and visibility for each product in the ecosystem."
      requirePermission="content:manage"
      actions={
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4" /> New product
        </Button>
      }
    >
      {loading ? (
        <TableSkeleton rows={6} cols={5} />
      ) : (
        <DataTable columns={columns} rows={data ?? []} loading={false} empty="No products yet." />
      )}

      <FormDialog
        open={open}
        onOpenChange={setOpen}
        title={editing ? `Edit ${editing.name}` : "New product"}
        description="Slug must be lowercase and URL-friendly. Status controls how the product appears on the public site."
        onSubmit={onSubmit}
        size="lg"
        submitLabel={editing ? "Save changes" : "Create product"}
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="slug">Slug *</Label>
            <Input id="slug" name="slug" required defaultValue={editing?.slug} placeholder="quatapay" />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="name">Name *</Label>
            <Input id="name" name="name" required defaultValue={editing?.name} />
          </div>
        </div>
        <div className="grid gap-2">
          <Label htmlFor="tagline">Tagline *</Label>
          <Input id="tagline" name="tagline" required defaultValue={editing?.tagline} />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="description">Description</Label>
          <Textarea id="description" name="description" rows={4} defaultValue={editing?.description} />
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="grid gap-2 sm:col-span-2">
            <Label htmlFor="category">Category *</Label>
            <Input id="category" name="category" required defaultValue={editing?.category} />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="status">Status</Label>
            <Select id="status" name="status" defaultValue={editing?.status ?? "coming_soon"}>
              <option value="live">Live</option>
              <option value="beta">Beta</option>
              <option value="coming_soon">Coming soon</option>
            </Select>
          </div>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            name="is_published"
            defaultChecked={editing?.is_published ?? true}
            className="h-4 w-4 rounded border-border"
          />
          Publish to the public site
        </label>
      </FormDialog>

      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(v) => !v && setDeleting(null)}
        title={`Remove ${deleting?.name ?? "product"}?`}
        description="This removes the product from the public site and the admin. This can't be undone."
        confirmLabel="Remove"
        destructive
        onConfirm={onDelete}
      />
    </PageShell>
  );
}
