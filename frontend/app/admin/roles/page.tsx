"use client";

import * as React from "react";
import { Pencil, Plus, Shield, Trash2 } from "lucide-react";
import { PageShell } from "@/components/admin/page-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { FormDialog } from "@/components/admin/form-dialog";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { CardSkeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/admin/empty-state";
import { useApi, useApiAction } from "@/lib/use-api";
import { useToast } from "@/components/ui/toast";

type Role = {
  id: number;
  slug: string;
  name: string;
  description: string | null;
  permissions: string[];
};

type Permission = {
  key: string;
  label: string;
  group: string;
};

export default function RolesPage() {
  const roles = useApi<Role[]>("/admin/roles");
  const perms = useApi<Permission[]>("/admin/permissions");
  const action = useApiAction();
  const toast = useToast();

  const [open, setOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<Role | null>(null);
  const [deleting, setDeleting] = React.useState<Role | null>(null);
  const [selected, setSelected] = React.useState<string[]>([]);

  function startCreate() {
    setEditing(null);
    setSelected([]);
    setOpen(true);
  }

  function startEdit(role: Role) {
    setEditing(role);
    setSelected(role.permissions);
    setOpen(true);
  }

  function togglePerm(key: string) {
    setSelected((prev) =>
      prev.includes(key) ? prev.filter((p) => p !== key) : [...prev, key]
    );
  }

  async function onSubmit(form: FormData) {
    const payload: Record<string, unknown> = {
      name: String(form.get("name")),
      description: String(form.get("description") || "") || null,
      permissions: selected,
    };
    if (!editing) payload.slug = String(form.get("slug"));
    try {
      if (editing) {
        await action(`/admin/roles/${editing.id}`, { method: "PUT", body: JSON.stringify(payload) });
        toast.success("Role updated", payload.name as string);
      } else {
        await action("/admin/roles", { method: "POST", body: JSON.stringify(payload) });
        toast.success("Role created", payload.name as string);
      }
      setOpen(false);
      roles.refresh();
    } catch (err) {
      toast.error("Couldn't save", err instanceof Error ? err.message : "Try again.");
    }
  }

  async function onDelete() {
    if (!deleting) return;
    try {
      await action(`/admin/roles/${deleting.id}`, { method: "DELETE" });
      toast.success("Role removed", deleting.name);
      roles.refresh();
    } catch (err) {
      toast.error("Couldn't delete", err instanceof Error ? err.message : "Try again.");
    } finally {
      setDeleting(null);
    }
  }

  const groupedPerms = React.useMemo(() => {
    const out: Record<string, Permission[]> = {};
    for (const p of perms.data ?? []) {
      (out[p.group] ??= []).push(p);
    }
    return out;
  }, [perms.data]);

  return (
    <PageShell
      title="Roles & permissions"
      description="Fine-grained RBAC across content, staff, messaging and system access."
      requirePermission="rbac:manage"
      actions={
        <Button onClick={startCreate}>
          <Plus className="h-4 w-4" /> New role
        </Button>
      }
    >
      {roles.loading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 4 }).map((_, i) => <CardSkeleton key={i} />)}
        </div>
      ) : (roles.data?.length ?? 0) === 0 ? (
        <EmptyState
          icon={Shield}
          title="No roles yet"
          description="Create roles to control what your team can access in the admin."
          action={
            <Button onClick={startCreate}>
              <Plus className="h-4 w-4" /> Create role
            </Button>
          }
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {(roles.data ?? []).map((r) => (
            <div key={r.id} className="rounded-2xl border border-border bg-card p-5 ring-soft">
              <div className="flex items-start justify-between">
                <div>
                  <div className="text-base font-semibold">{r.name}</div>
                  <code className="text-[11px] text-muted-foreground">{r.slug}</code>
                </div>
                <Badge variant="brand">{r.permissions.length}</Badge>
              </div>
              <p className="mt-2 text-sm text-muted-foreground line-clamp-2">{r.description}</p>
              <div className="mt-4 flex flex-wrap gap-1">
                {r.permissions.slice(0, 6).map((p) => (
                  <span
                    key={p}
                    className="inline-flex items-center rounded-md border border-border bg-surface px-2 py-0.5 text-[10px] font-mono"
                  >
                    {p}
                  </span>
                ))}
                {r.permissions.length > 6 && (
                  <span className="text-[10px] text-muted-foreground">+{r.permissions.length - 6} more</span>
                )}
              </div>
              <div className="mt-5 flex justify-end gap-1 border-t border-border pt-3">
                {r.slug !== "super_admin" ? (
                  <>
                    <Button size="sm" variant="ghost" onClick={() => startEdit(r)}>
                      <Pencil className="h-3.5 w-3.5" /> Edit
                    </Button>
                    <Button size="sm" variant="ghost" className="text-rose-700" onClick={() => setDeleting(r)}>
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </>
                ) : (
                  <span className="text-[11px] text-muted-foreground italic">Immutable</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <FormDialog
        open={open}
        onOpenChange={setOpen}
        title={editing ? `Edit ${editing.name}` : "New role"}
        description="Toggle permissions to control what holders of this role can see and do."
        onSubmit={onSubmit}
        size="xl"
        submitLabel={editing ? "Save changes" : "Create role"}
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="slug">Slug *</Label>
            <Input
              id="slug"
              name="slug"
              required
              defaultValue={editing?.slug}
              disabled={!!editing}
              placeholder="lowercase_snake"
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="name">Name *</Label>
            <Input id="name" name="name" required defaultValue={editing?.name} placeholder="Manager" />
          </div>
        </div>
        <div className="grid gap-2">
          <Label htmlFor="description">Description</Label>
          <Input id="description" name="description" defaultValue={editing?.description ?? ""} placeholder="What this role can do" />
        </div>

        <div>
          <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
            Permissions ({selected.length}/{perms.data?.length ?? 0})
          </div>
          {perms.loading ? (
            <div className="text-sm text-muted-foreground">Loading…</div>
          ) : (
            <div className="space-y-4">
              {Object.entries(groupedPerms).map(([group, items]) => (
                <div key={group}>
                  <div className="text-[11px] uppercase tracking-wider text-muted-foreground mb-2">
                    {group}
                  </div>
                  <div className="grid sm:grid-cols-2 gap-2">
                    {items.map((p) => {
                      const checked = selected.includes(p.key);
                      return (
                        <label
                          key={p.key}
                          className={`flex cursor-pointer items-start gap-3 rounded-xl border p-3 transition ${
                            checked ? "border-primary/40 bg-brand-soft/30" : "border-border bg-surface hover:bg-surface-soft"
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => togglePerm(p.key)}
                            className="mt-1 h-4 w-4"
                          />
                          <div className="min-w-0">
                            <div className="text-sm font-medium">{p.label}</div>
                            <code className="text-[10px] text-muted-foreground">{p.key}</code>
                          </div>
                        </label>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </FormDialog>

      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(v) => !v && setDeleting(null)}
        title={`Delete role ${deleting?.name ?? ""}?`}
        description="If any users are assigned to this role, deletion will be blocked. Reassign first."
        confirmLabel="Delete"
        destructive
        onConfirm={onDelete}
      />
    </PageShell>
  );
}
