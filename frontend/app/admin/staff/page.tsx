"use client";

import * as React from "react";
import Link from "next/link";
import { Eye, Pencil, Plus, Trash2 } from "lucide-react";
import { PageShell } from "@/components/admin/page-shell";
import { DataTable, type Column } from "@/components/admin/data-table";
import { FormDialog } from "@/components/admin/form-dialog";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password-input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { TableSkeleton } from "@/components/ui/skeleton";
import { SearchInput, useDebouncedValue } from "@/components/admin/search-input";
import { useApi, useApiAction } from "@/lib/use-api";
import { useToast } from "@/components/ui/toast";

type Staff = {
  id: number;
  full_name: string;
  email: string;
  role: string;
  department: string | null;
  status: "active" | "invited" | "suspended";
  job_title: string | null;
};

type Dept = { id: number; slug: string; name: string };
type Role = { id: number; slug: string; name: string };

const statusVariant: Record<Staff["status"], "success" | "warn" | "danger"> = {
  active: "success",
  invited: "warn",
  suspended: "danger",
};

export default function StaffPage() {
  const staff = useApi<Staff[]>("/admin/staff");
  const departments = useApi<Dept[]>("/admin/departments");
  const roles = useApi<Role[]>("/admin/roles");
  const action = useApiAction();
  const toast = useToast();

  const [search, setSearch] = React.useState("");
  const debounced = useDebouncedValue(search);

  const [open, setOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<Staff | null>(null);
  const [deleting, setDeleting] = React.useState<Staff | null>(null);

  const filtered = React.useMemo(() => {
    const list = staff.data ?? [];
    if (!debounced.trim()) return list;
    const q = debounced.toLowerCase();
    return list.filter((s) =>
      [s.full_name, s.email, s.role, s.department ?? "", s.job_title ?? ""]
        .join(" ").toLowerCase().includes(q)
    );
  }, [staff.data, debounced]);

  async function onSubmit(form: FormData) {
    const dept = String(form.get("department_slug") || "");
    const payload: Record<string, unknown> = {
      full_name: String(form.get("full_name")),
      email: String(form.get("email")),
      role_slug: String(form.get("role_slug")),
      department_slug: dept || null,
      job_title: String(form.get("job_title") || "") || null,
      phone: String(form.get("phone") || "") || null,
      biometric_id: String(form.get("biometric_id") || "") || null,
    };
    const password = String(form.get("password") || "").trim();
    if (password) payload.password = password;

    try {
      if (editing) {
        await action(`/admin/staff/${editing.id}`, { method: "PUT", body: JSON.stringify(payload) });
        toast.success("Employee updated", payload.full_name as string);
      } else {
        await action("/admin/staff", { method: "POST", body: JSON.stringify(payload) });
        toast.success("Employee invited", `${payload.full_name} <${payload.email}>`);
      }
      setOpen(false);
      staff.refresh();
    } catch (err) {
      toast.error("Couldn't save", err instanceof Error ? err.message : "Try again.");
    }
  }

  async function onDelete() {
    if (!deleting) return;
    try {
      await action(`/admin/staff/${deleting.id}`, { method: "DELETE" });
      toast.success("Employee suspended", deleting.full_name);
      staff.refresh();
    } catch (err) {
      toast.error("Couldn't suspend", err instanceof Error ? err.message : "Try again.");
    } finally {
      setDeleting(null);
    }
  }

  const cols: Column<Staff>[] = [
    {
      key: "name",
      header: "Employee",
      cell: (r) => (
        <Link href={`/admin/staff/${r.id}`} className="flex items-center gap-3 group">
          <div className="h-9 w-9 rounded-full bg-brand-soft text-primary inline-flex items-center justify-center text-xs font-semibold">
            {r.full_name.split(" ").map((p) => p[0]).slice(0, 2).join("")}
          </div>
          <div>
            <div className="font-medium group-hover:text-primary transition-colors">{r.full_name}</div>
            <div className="text-xs text-muted-foreground">{r.email}</div>
          </div>
        </Link>
      ),
    },
    { key: "role", header: "Role", cell: (r) => <Badge variant="brand">{r.role.replace("_", " ")}</Badge> },
    { key: "title", header: "Title", cell: (r) => r.job_title ?? "—" },
    { key: "dept", header: "Department", cell: (r) => r.department ?? "—" },
    {
      key: "status",
      header: "Status",
      cell: (r) => (
        <Badge variant={statusVariant[r.status]} className="capitalize">{r.status}</Badge>
      ),
    },
    {
      key: "actions",
      header: "",
      className: "w-44 text-right",
      cell: (r) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="ghost" asChild>
            <Link href={`/admin/staff/${r.id}`}>
              <Eye className="h-3.5 w-3.5" />
            </Link>
          </Button>
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
      title="Employees"
      description="Manage staff profiles, roles, departments and status."
      requirePermission="staff:manage"
      actions={
        <>
          <SearchInput value={search} onChange={setSearch} placeholder="Search employees…" />
          <Button onClick={() => { setEditing(null); setOpen(true); }}>
            <Plus className="h-4 w-4" /> Invite employee
          </Button>
        </>
      }
    >
      {staff.loading ? (
        <TableSkeleton rows={6} cols={6} />
      ) : (
        <DataTable columns={cols} rows={filtered} loading={false} empty="No employees match." />
      )}

      <FormDialog
        open={open}
        onOpenChange={setOpen}
        title={editing ? `Edit ${editing.full_name}` : "Invite employee"}
        description={editing ? undefined : "If you don't set a password, an invite-style account is created and a temporary one is generated."}
        onSubmit={onSubmit}
        size="lg"
        submitLabel={editing ? "Save changes" : "Send invite"}
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="full_name">Full name *</Label>
            <Input id="full_name" name="full_name" required defaultValue={editing?.full_name} placeholder="Jane Doe" autoComplete="name" />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="email">Work email *</Label>
            <Input id="email" name="email" type="email" required defaultValue={editing?.email} disabled={!!editing} placeholder="jane@quatadigital.com" autoComplete="email" />
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="role_slug">Role *</Label>
            <Select id="role_slug" name="role_slug" required defaultValue={editing?.role ?? "staff"}>
              {(roles.data ?? []).map((r) => (
                <option key={r.slug} value={r.slug}>{r.name}</option>
              ))}
            </Select>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="department_slug">Department</Label>
            <Select
              id="department_slug"
              name="department_slug"
              defaultValue={(departments.data ?? []).find((d) => d.name === editing?.department)?.slug ?? ""}
            >
              <option value="">— None —</option>
              {(departments.data ?? []).map((d) => (
                <option key={d.slug} value={d.slug}>{d.name}</option>
              ))}
            </Select>
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="job_title">Job title</Label>
            <Input id="job_title" name="job_title" defaultValue={editing?.job_title ?? ""} placeholder="e.g. Partnerships Lead" />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="phone">Phone</Label>
            <Input id="phone" name="phone" type="tel" placeholder="+237 6 7000 0000" autoComplete="tel" />
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="biometric_id">Biometric ID</Label>
            <Input id="biometric_id" name="biometric_id" placeholder="Maps to device ID" />
          </div>
          {!editing && (
            <div className="grid gap-2">
              <Label htmlFor="password">Password (optional)</Label>
              <PasswordInput id="password" name="password" placeholder="Auto-generate if blank" autoComplete="new-password" />
            </div>
          )}
        </div>
      </FormDialog>

      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(v) => !v && setDeleting(null)}
        title={`Suspend ${deleting?.full_name ?? "employee"}?`}
        description="They'll be marked inactive and unable to sign in. You can reactivate them later."
        confirmLabel="Suspend"
        destructive
        onConfirm={onDelete}
      />
    </PageShell>
  );
}
