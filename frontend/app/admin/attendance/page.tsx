"use client";

import * as React from "react";
import { Clock, MapPin } from "lucide-react";
import { PageShell } from "@/components/admin/page-shell";
import { DataTable, type Column } from "@/components/admin/data-table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { useApi, useApiAction } from "@/lib/use-api";
import { useToast } from "@/components/ui/toast";
import { TableSkeleton } from "@/components/ui/skeleton";

type AttendanceLog = {
  id: number;
  staff_name: string;
  check_in_at: string | null;
  check_out_at: string | null;
  source: "manual" | "biometric" | "gps" | "web";
  device_name: string | null;
  status: "present" | "late" | "absent" | "on_leave";
};

const variant: Record<AttendanceLog["status"], "success" | "warn" | "danger" | "brand"> = {
  present: "success",
  late: "warn",
  absent: "danger",
  on_leave: "brand",
};

export default function AttendancePage() {
  const { data, loading, refresh } = useApi<AttendanceLog[]>("/admin/attendance");
  const action = useApiAction();
  const toast = useToast();
  const [submitting, setSubmitting] = React.useState(false);

  async function checkIn(method: "in" | "out") {
    setSubmitting(true);
    try {
      await action(`/attendance/${method}`, {
        method: "POST",
        body: JSON.stringify({ source: "web" }),
      });
      toast.success(method === "in" ? "Checked in" : "Checked out");
      refresh();
    } catch (err) {
      toast.error("Couldn't update attendance", err instanceof Error ? err.message : "Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  const columns: Column<AttendanceLog>[] = [
    { key: "name", header: "Employee", cell: (r) => <span className="font-medium">{r.staff_name}</span> },
    { key: "in", header: "Check-in", cell: (r) => r.check_in_at ? new Date(r.check_in_at).toLocaleTimeString() : "—" },
    { key: "out", header: "Check-out", cell: (r) => r.check_out_at ? new Date(r.check_out_at).toLocaleTimeString() : "—" },
    { key: "src", header: "Source", cell: (r) => (
      <Badge variant="outline" className="capitalize">{r.source}</Badge>
    ) },
    { key: "dev", header: "Device", cell: (r) => r.device_name ?? "—" },
    { key: "status", header: "Status", cell: (r) => (
      <Badge variant={variant[r.status]} className="capitalize">{r.status.replace("_", " ")}</Badge>
    ) },
  ];

  return (
    <PageShell
      title="Attendance"
      description="Manual check-in/out, biometric devices and mobile GPS — all logged in one place."
      actions={
        <>
          <Button onClick={() => checkIn("in")} disabled={submitting}>
            <Clock className="h-4 w-4" /> Check in
          </Button>
          <Button variant="outline" onClick={() => checkIn("out")} disabled={submitting}>
            Check out
          </Button>
        </>
      }
    >
      <Tabs defaultValue="today">
        <TabsList>
          <TabsTrigger value="today">Today</TabsTrigger>
          <TabsTrigger value="week">This week</TabsTrigger>
        </TabsList>
        <TabsContent value="today">
          {loading ? (
            <TableSkeleton rows={6} cols={6} />
          ) : (
            <DataTable columns={columns} rows={data ?? []} loading={false} />
          )}
        </TabsContent>
        <TabsContent value="week">
          <div className="rounded-2xl border border-border bg-card p-8 text-center text-sm text-muted-foreground">
            Weekly aggregation will appear here once the backend reporter runs.
          </div>
        </TabsContent>
      </Tabs>

      <div className="mt-6 rounded-2xl border border-border bg-surface-soft p-5">
        <div className="flex items-start gap-3">
          <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-brand-soft text-primary">
            <MapPin className="h-5 w-5" />
          </div>
          <div>
            <div className="text-sm font-semibold">Biometric & GPS ready</div>
            <p className="mt-1 text-sm text-muted-foreground max-w-xl">
              Devices are configured under <strong>Biometric devices</strong>. The
              attendance API accepts logs from biometric devices, mobile GPS
              check-ins and the web — all flow into the same log.
            </p>
          </div>
        </div>
      </div>
    </PageShell>
  );
}
