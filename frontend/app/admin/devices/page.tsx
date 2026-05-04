"use client";

import * as React from "react";
import { Pencil, Plus, RefreshCw, Trash2 } from "lucide-react";
import { PageShell } from "@/components/admin/page-shell";
import { DataTable, type Column } from "@/components/admin/data-table";
import { FormDialog } from "@/components/admin/form-dialog";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { TableSkeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/admin/empty-state";
import { useApi, useApiAction } from "@/lib/use-api";
import { useToast } from "@/components/ui/toast";

type Device = {
  id: number;
  name: string;
  vendor: string;
  ip_address: string | null;
  api_endpoint: string | null;
  location: string;
  status: "online" | "offline" | "syncing";
  last_sync_at: string | null;
  api_token?: string | null;
};

const variant: Record<Device["status"], "success" | "danger" | "warn"> = {
  online: "success",
  offline: "danger",
  syncing: "warn",
};

export default function DevicesPage() {
  const { data, loading, refresh } = useApi<Device[]>("/admin/devices");
  const action = useApiAction();
  const toast = useToast();

  const [open, setOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<Device | null>(null);
  const [deleting, setDeleting] = React.useState<Device | null>(null);
  const [showToken, setShowToken] = React.useState<Device | null>(null);

  async function onSubmit(form: FormData) {
    const payload = {
      name: String(form.get("name")),
      vendor: String(form.get("vendor") || "Generic"),
      ip_address: String(form.get("ip_address") || "") || null,
      api_endpoint: String(form.get("api_endpoint") || "") || null,
      location: String(form.get("location") || "HQ"),
    };
    try {
      if (editing) {
        await action(`/admin/devices/${editing.id}`, { method: "PUT", body: JSON.stringify(payload) });
        toast.success("Device updated", payload.name);
      } else {
        const created = await action<Device>("/admin/devices", { method: "POST", body: JSON.stringify(payload) });
        toast.success("Device added", payload.name);
        setShowToken(created);
      }
      setOpen(false);
      refresh();
    } catch (err) {
      toast.error("Couldn't save", err instanceof Error ? err.message : "Try again.");
    }
  }

  async function onRotate(d: Device) {
    try {
      const updated = await action<Device>(`/admin/devices/${d.id}/rotate`, { method: "POST" });
      toast.success("Token rotated", "Update the device with the new token.");
      setShowToken(updated);
      refresh();
    } catch (err) {
      toast.error("Couldn't rotate", err instanceof Error ? err.message : "Try again.");
    }
  }

  async function onDelete() {
    if (!deleting) return;
    try {
      await action(`/admin/devices/${deleting.id}`, { method: "DELETE" });
      toast.success("Device removed", deleting.name);
      refresh();
    } catch (err) {
      toast.error("Couldn't delete", err instanceof Error ? err.message : "Try again.");
    } finally {
      setDeleting(null);
    }
  }

  const cols: Column<Device>[] = [
    { key: "name", header: "Device", cell: (r) => <span className="font-medium">{r.name}</span> },
    { key: "vendor", header: "Vendor", cell: (r) => r.vendor },
    {
      key: "ip",
      header: "IP / endpoint",
      cell: (r) => <code className="text-xs text-muted-foreground">{r.api_endpoint || r.ip_address || "—"}</code>,
    },
    { key: "loc", header: "Location", cell: (r) => r.location },
    {
      key: "sync",
      header: "Last sync",
      cell: (r) => (r.last_sync_at ? new Date(r.last_sync_at).toLocaleString() : "—"),
    },
    {
      key: "status",
      header: "Status",
      cell: (r) => <Badge variant={variant[r.status]} className="capitalize">{r.status}</Badge>,
    },
    {
      key: "actions",
      header: "",
      className: "w-44 text-right",
      cell: (r) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="ghost" onClick={() => onRotate(r)}>
            <RefreshCw className="h-3.5 w-3.5" />
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
      title="Biometric devices"
      description="Vendor-agnostic. Each device gets an API token used to authenticate webhook batches sent to /api/v1/devices/{id}/sync."
      requirePermission="devices:manage"
      actions={
        <Button onClick={() => { setEditing(null); setOpen(true); }}>
          <Plus className="h-4 w-4" /> Add device
        </Button>
      }
    >
      {loading ? (
        <TableSkeleton rows={4} cols={7} />
      ) : (data?.length ?? 0) === 0 ? (
        <EmptyState
          icon={Plus}
          title="No biometric devices yet"
          description="Add your first device to start accepting attendance webhook events."
          action={
            <Button onClick={() => { setEditing(null); setOpen(true); }}>
              <Plus className="h-4 w-4" /> Add device
            </Button>
          }
        />
      ) : (
        <DataTable columns={cols} rows={data ?? []} loading={false} />
      )}

      <FormDialog
        open={open}
        onOpenChange={setOpen}
        title={editing ? `Edit ${editing.name}` : "Add device"}
        description="On create, an API token is generated and shown once."
        onSubmit={onSubmit}
        submitLabel={editing ? "Save changes" : "Create"}
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="name">Name *</Label>
            <Input id="name" name="name" required defaultValue={editing?.name} />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="vendor">Vendor</Label>
            <Input id="vendor" name="vendor" defaultValue={editing?.vendor ?? "Generic"} />
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="ip_address">IP address</Label>
            <Input id="ip_address" name="ip_address" defaultValue={editing?.ip_address ?? ""} />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="api_endpoint">API endpoint</Label>
            <Input id="api_endpoint" name="api_endpoint" defaultValue={editing?.api_endpoint ?? ""} />
          </div>
        </div>
        <div className="grid gap-2">
          <Label htmlFor="location">Location</Label>
          <Input id="location" name="location" defaultValue={editing?.location ?? "HQ"} />
        </div>
      </FormDialog>

      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(v) => !v && setDeleting(null)}
        title={`Remove ${deleting?.name ?? "device"}?`}
        description="The device will stop syncing immediately."
        confirmLabel="Remove"
        destructive
        onConfirm={onDelete}
      />

      <TokenDialog device={showToken} onClose={() => setShowToken(null)} />
    </PageShell>
  );
}

function TokenDialog({ device, onClose }: { device: Device | null; onClose: () => void }) {
  const toast = useToast();
  const open = !!device;
  if (!device || !device.api_token) return null;
  return (
    <ConfirmDialog
      open={open}
      onOpenChange={(v) => !v && onClose()}
      title={`API token for ${device.name}`}
      description={
        "Copy this token now — it won't be shown again. Configure it on the device under X-Device-Token header for /api/v1/devices/" +
        device.id +
        "/sync."
      }
      confirmLabel="Copy & close"
      cancelLabel="Close"
      onConfirm={async () => {
        if (device.api_token) {
          try {
            await navigator.clipboard.writeText(device.api_token);
            toast.success("Token copied");
          } catch {
            toast.info("Couldn't copy", device.api_token);
          }
        }
        onClose();
      }}
    />
  );
}
