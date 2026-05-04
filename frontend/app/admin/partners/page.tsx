"use client";

import * as React from "react";
import { Download, Eye, Handshake } from "lucide-react";
import { PageShell } from "@/components/admin/page-shell";
import { DataTable, BulkActionsBar, type Column } from "@/components/admin/data-table";
import { TableSkeleton } from "@/components/ui/skeleton";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Pagination } from "@/components/admin/pagination";
import { SearchInput, useDebouncedValue } from "@/components/admin/search-input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { EmptyState } from "@/components/admin/empty-state";
import { PartnerDetailSlideOver } from "@/components/admin/partner-detail";
import { useApi, useApiAction } from "@/lib/use-api";
import { useToast } from "@/components/ui/toast";

type Partner = {
  id: number;
  partner_type: "business" | "strategic" | "investor" | "service";
  status: "new" | "in_review" | "approved" | "rejected";
  payload: Record<string, string>;
  created_at: string;
};

const statusVariant: Record<Partner["status"], "default" | "warn" | "success" | "danger"> = {
  new: "default",
  in_review: "warn",
  approved: "success",
  rejected: "danger",
};

export default function PartnersAdminPage() {
  const [type, setType] = React.useState<string>("");
  const [statusFilter, setStatusFilter] = React.useState<string>("");
  const [page, setPage] = React.useState(1);
  const [pageSize] = React.useState(25);
  const [search, setSearch] = React.useState("");
  const debounced = useDebouncedValue(search);

  const params = new URLSearchParams();
  if (type) params.set("partner_type", type);
  if (statusFilter) params.set("status", statusFilter);
  if (debounced) params.set("q", debounced);
  params.set("page", String(page));
  params.set("page_size", String(pageSize));
  const path = `/admin/partners?${params.toString()}`;

  const { data, loading, refresh } = useApi<Partner[]>(path);
  const action = useApiAction();
  const toast = useToast();

  const [openDetail, setOpenDetail] = React.useState(false);
  const [detailId, setDetailId] = React.useState<number | null>(null);
  const [selected, setSelected] = React.useState<number[]>([]);
  const [confirmBulk, setConfirmBulk] = React.useState<{
    status: Partner["status"];
    label: string;
    destructive?: boolean;
  } | null>(null);

  function viewDetail(id: number) {
    setDetailId(id);
    setOpenDetail(true);
  }

  React.useEffect(() => { setPage(1); setSelected([]); }, [type, statusFilter, debounced]);

  async function setStatus(id: number, status: Partner["status"]) {
    try {
      await action(`/admin/partners/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      toast.success("Updated", `Status set to ${status.replace("_", " ")}.`);
      refresh();
    } catch (err) {
      toast.error("Couldn't update", err instanceof Error ? err.message : "Try again.");
    }
  }

  async function bulkSetStatus(status: Partner["status"]) {
    if (selected.length === 0) return;
    let ok = 0;
    let fail = 0;
    await Promise.all(
      selected.map((id) =>
        action(`/admin/partners/${id}`, {
          method: "PATCH",
          body: JSON.stringify({ status }),
        })
          .then(() => ok++)
          .catch(() => fail++)
      )
    );
    toast.success(
      `Bulk update`,
      fail === 0 ? `${ok} request${ok === 1 ? "" : "s"} updated.` : `${ok} updated, ${fail} failed.`
    );
    setSelected([]);
    refresh();
  }

  const columns: Column<Partner>[] = [
    {
      key: "name",
      header: "Applicant",
      cell: (r) => (
        <div>
          <div className="font-medium">
            {r.payload.company_name ?? r.payload.full_name ?? r.payload.name ?? "—"}
          </div>
          <div className="text-xs text-muted-foreground">
            {r.payload.email ?? r.payload.phone ?? ""}
          </div>
        </div>
      ),
    },
    {
      key: "type",
      header: "Path",
      cell: (r) => <Badge variant="brand" className="capitalize">{r.partner_type}</Badge>,
    },
    {
      key: "country",
      header: "Country / city",
      cell: (r) => r.payload.country ?? r.payload.city ?? "—",
    },
    {
      key: "submitted",
      header: "Submitted",
      cell: (r) => (
        <span className="text-muted-foreground text-xs">
          {new Date(r.created_at).toLocaleString()}
        </span>
      ),
    },
    {
      key: "status",
      header: "Status",
      cell: (r) => (
        <Badge variant={statusVariant[r.status]} className="capitalize">
          {r.status.replace("_", " ")}
        </Badge>
      ),
    },
    {
      key: "actions",
      header: "Actions",
      cell: (r) => (
        <div className="flex gap-1">
          <Button size="sm" variant="outline" onClick={() => viewDetail(r.id)}>
            <Eye className="h-3.5 w-3.5" /> View
          </Button>
          <Button size="sm" onClick={() => setStatus(r.id, "approved")}>
            Approve
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="text-rose-700"
            onClick={() => setStatus(r.id, "rejected")}
          >
            Reject
          </Button>
        </div>
      ),
    },
  ];

  return (
    <PageShell
      title="Partner requests"
      description="Review, filter and triage incoming partner applications."
      requirePermission="partners:manage"
      actions={
        <>
          <SearchInput value={search} onChange={setSearch} placeholder="Search by company, name, email…" />
          <Select value={type} onChange={(e) => setType(e.target.value)} className="w-40">
            <option value="">All paths</option>
            <option value="business">Business</option>
            <option value="strategic">Strategic</option>
            <option value="investor">Investor</option>
            <option value="service">Service</option>
          </Select>
          <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="w-36">
            <option value="">All statuses</option>
            <option value="new">New</option>
            <option value="in_review">In review</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
          </Select>
          <Button asChild variant="outline">
            <a
              href={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"}/admin/partners/export.csv`}
              target="_blank"
              rel="noreferrer"
            >
              <Download className="h-4 w-4" /> Export CSV
            </a>
          </Button>
        </>
      }
    >
      <BulkActionsBar count={selected.length} onClear={() => setSelected([])}>
        <Button size="sm" variant="outline" onClick={() => setConfirmBulk({ status: "in_review", label: "mark in review" })}>
          Mark in review
        </Button>
        <Button size="sm" onClick={() => setConfirmBulk({ status: "approved", label: "approve" })}>
          Approve
        </Button>
        <Button
          size="sm"
          variant="ghost"
          className="text-rose-700"
          onClick={() => setConfirmBulk({ status: "rejected", label: "reject", destructive: true })}
        >
          Reject
        </Button>
      </BulkActionsBar>

      {loading ? (
        <TableSkeleton rows={6} cols={7} />
      ) : (data?.length ?? 0) === 0 ? (
        <EmptyState
          icon={Handshake}
          title="No partner requests match"
          description="Try clearing the filters or wait for new applications to land."
        />
      ) : (
        <DataTable
          columns={columns}
          rows={data ?? []}
          loading={false}
          selectable
          selectedIds={selected}
          onSelectionChange={setSelected}
        />
      )}
      <Pagination
        page={page}
        pageSize={pageSize}
        total={(data?.length ?? 0) + (page - 1) * pageSize}
        onPageChange={setPage}
      />

      <PartnerDetailSlideOver
        open={openDetail}
        onOpenChange={setOpenDetail}
        partnerId={detailId}
        onChanged={refresh}
      />

      <ConfirmDialog
        open={!!confirmBulk}
        onOpenChange={(v) => !v && setConfirmBulk(null)}
        title={`Bulk ${confirmBulk?.label ?? "update"}`}
        description={`This will ${confirmBulk?.label} ${selected.length} request${selected.length === 1 ? "" : "s"}. Applicants will receive an email notification.`}
        confirmLabel={confirmBulk?.label ?? "Apply"}
        destructive={confirmBulk?.destructive}
        onConfirm={async () => {
          if (confirmBulk) await bulkSetStatus(confirmBulk.status);
          setConfirmBulk(null);
        }}
      />
    </PageShell>
  );
}
