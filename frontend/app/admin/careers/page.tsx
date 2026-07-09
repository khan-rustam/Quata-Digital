"use client";

import * as React from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { PageShell } from "@/components/admin/page-shell";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { DataTable, type Column } from "@/components/admin/data-table";
import { FormDialog } from "@/components/admin/form-dialog";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select } from "@/components/ui/select";
import { TableSkeleton } from "@/components/ui/skeleton";
import { ApplicationDetailSlideOver } from "@/components/admin/application-detail";
import { useApi, useApiAction } from "@/lib/use-api";
import { useToast } from "@/components/ui/toast";
import { formatDate } from "@/lib/utils";
import { stageLabel, stageVariant } from "@/lib/applicant-stages";

type Job = {
  id: number;
  slug: string;
  title: string;
  department: string;
  location: string;
  employment_type: string;
  summary: string;
  description: string;
  responsibilities: string[];
  requirements: string[];
  is_published: boolean;
  applications_count: number;
};

type Application = {
  id: number;
  full_name: string;
  email: string;
  job_title: string;
  status: string;
  created_at: string;
};

function readApplicantParam(): number | null {
  if (typeof window === "undefined") return null;
  const a = new URLSearchParams(window.location.search).get("applicant");
  return a && /^\d+$/.test(a) ? Number(a) : null;
}

export default function CareersAdminPage() {
  // Deep link from the "new applicant" email (/admin/careers?applicant=<id>).
  // Read once as initial state — admin pages render client-side behind auth
  // (PageShell gates on useAuth), so window exists and there's no SSR mismatch.
  const [initialApplicant] = React.useState<number | null>(readApplicantParam);
  const [tab, setTab] = React.useState<string>(initialApplicant != null ? "apps" : "jobs");

  return (
    <PageShell
      title="Careers"
      description="Create job listings, publish to the site and track applicants."
      requirePermission="careers:manage"
    >
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="jobs">Jobs</TabsTrigger>
          <TabsTrigger value="apps">Applicants</TabsTrigger>
        </TabsList>
        <TabsContent value="jobs">
          <JobsManager />
        </TabsContent>
        <TabsContent value="apps">
          <ApplicantsManager initialApplicant={initialApplicant} />
        </TabsContent>
      </Tabs>
    </PageShell>
  );
}

function JobsManager() {
  const jobs = useApi<Job[]>("/admin/jobs");
  const action = useApiAction();
  const toast = useToast();
  const [open, setOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<Job | null>(null);
  const [deleting, setDeleting] = React.useState<Job | null>(null);

  async function onSubmit(form: FormData) {
    const payload = {
      slug: String(form.get("slug")),
      title: String(form.get("title")),
      department: String(form.get("department")),
      location: String(form.get("location")),
      employment_type: String(form.get("employment_type")),
      summary: String(form.get("summary")),
      description: String(form.get("description")),
      responsibilities: String(form.get("responsibilities") || "")
        .split("\n").map((s) => s.trim()).filter(Boolean),
      requirements: String(form.get("requirements") || "")
        .split("\n").map((s) => s.trim()).filter(Boolean),
      is_published: form.get("is_published") === "on",
    };
    try {
      if (editing) {
        await action(`/admin/jobs/${editing.id}`, { method: "PUT", body: JSON.stringify(payload) });
        toast.success("Job updated", payload.title);
      } else {
        await action("/admin/jobs", { method: "POST", body: JSON.stringify(payload) });
        toast.success("Job posted", payload.title);
      }
      setOpen(false);
      jobs.refresh();
    } catch (err) {
      toast.error("Couldn't save", err instanceof Error ? err.message : "Try again.");
    }
  }

  async function onDelete() {
    if (!deleting) return;
    try {
      await action(`/admin/jobs/${deleting.id}`, { method: "DELETE" });
      toast.success("Job removed", deleting.title);
      jobs.refresh();
    } catch (err) {
      toast.error("Couldn't delete", err instanceof Error ? err.message : "Try again.");
    } finally {
      setDeleting(null);
    }
  }

  const cols: Column<Job>[] = [
    { key: "title", header: "Role", cell: (j) => <span className="font-medium">{j.title}</span> },
    { key: "dept", header: "Department", cell: (j) => j.department },
    { key: "loc", header: "Location", cell: (j) => j.location },
    { key: "type", header: "Type", cell: (j) => <Badge variant="outline">{j.employment_type}</Badge> },
    { key: "apps", header: "Applicants", cell: (j) => j.applications_count },
    {
      key: "pub",
      header: "Public",
      cell: (j) => (
        <Badge variant={j.is_published ? "success" : "outline"}>
          {j.is_published ? "Published" : "Draft"}
        </Badge>
      ),
    },
    {
      key: "actions",
      header: "",
      className: "w-32 text-right",
      cell: (j) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="ghost" onClick={() => { setEditing(j); setOpen(true); }}>
            <Pencil className="h-3.5 w-3.5" />
          </Button>
          <Button size="sm" variant="ghost" className="text-rose-700" onClick={() => setDeleting(j)}>
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      ),
    },
  ];

  return (
    <>
      <div className="mb-3 flex justify-end">
        <Button onClick={() => { setEditing(null); setOpen(true); }}>
          <Plus className="h-4 w-4" /> New job
        </Button>
      </div>
      {jobs.loading ? (
        <TableSkeleton rows={5} cols={7} />
      ) : (
        <DataTable columns={cols} rows={jobs.data ?? []} loading={false} />
      )}

      <FormDialog
        open={open}
        onOpenChange={setOpen}
        title={editing ? `Edit "${editing.title}"` : "New job"}
        onSubmit={onSubmit}
        size="xl"
        submitLabel={editing ? "Save changes" : "Publish job"}
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="slug">Slug *</Label>
            <Input id="slug" name="slug" required defaultValue={editing?.slug} placeholder="business-development-lead" />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="title">Title *</Label>
            <Input id="title" name="title" required defaultValue={editing?.title} placeholder="Business Development Lead" />
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="grid gap-2">
            <Label htmlFor="department">Department *</Label>
            <Input id="department" name="department" required defaultValue={editing?.department} placeholder="Marketing & Growth" />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="location">Location *</Label>
            <Input id="location" name="location" required defaultValue={editing?.location} placeholder="Bamenda, Cameroon (hybrid)" />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="employment_type">Type *</Label>
            <Select id="employment_type" name="employment_type" defaultValue={editing?.employment_type ?? "Full-time"}>
              <option>Full-time</option>
              <option>Part-time</option>
              <option>Contract</option>
              <option>Intern</option>
            </Select>
          </div>
        </div>
        <div className="grid gap-2">
          <Label htmlFor="summary">Summary *</Label>
          <Textarea id="summary" name="summary" rows={2} required defaultValue={editing?.summary} placeholder="One or two sentences shown on the careers index card." />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="description">Description *</Label>
          <Textarea id="description" name="description" rows={6} required defaultValue={editing?.description} placeholder="Full role description shown on the public job page. Markdown supported." />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="responsibilities">Responsibilities (one per line)</Label>
            <Textarea
              id="responsibilities"
              name="responsibilities"
              rows={5}
              defaultValue={editing?.responsibilities?.join("\n")}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="requirements">Requirements (one per line)</Label>
            <Textarea
              id="requirements"
              name="requirements"
              rows={5}
              defaultValue={editing?.requirements?.join("\n")}
            />
          </div>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            name="is_published"
            defaultChecked={editing?.is_published ?? true}
            className="h-4 w-4 rounded border-border"
          />
          Publish to the careers page
        </label>
      </FormDialog>

      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(v) => !v && setDeleting(null)}
        title={`Delete "${deleting?.title ?? "job"}"?`}
        description="The job and its applicants will be removed."
        confirmLabel="Delete"
        destructive
        onConfirm={onDelete}
      />
    </>
  );
}

function ApplicantsManager({ initialApplicant }: { initialApplicant: number | null }) {
  const apps = useApi<Application[]>("/admin/applications");
  // Deep link from the "new applicant" email opens that candidate's panel on
  // mount — the CV (view/download) and hiring dialogs live there.
  const [openDetail, setOpenDetail] = React.useState(initialApplicant != null);
  const [detailId, setDetailId] = React.useState<number | null>(initialApplicant);

  function viewDetail(id: number) {
    setDetailId(id);
    setOpenDetail(true);
  }

  const cols: Column<Application>[] = [
    {
      key: "name",
      header: "Candidate",
      cell: (a) => (
        <div>
          <div className="font-medium">{a.full_name}</div>
          <div className="text-xs text-muted-foreground">{a.email}</div>
        </div>
      ),
    },
    { key: "role", header: "Role", cell: (a) => a.job_title },
    {
      key: "status",
      header: "Status",
      cell: (a) => (
        <Badge variant={stageVariant(a.status)}>{stageLabel(a.status)}</Badge>
      ),
    },
    { key: "date", header: "Submitted", cell: (a) => formatDate(a.created_at) },
    {
      key: "actions",
      header: "",
      className: "w-28 text-right",
      // Review opens the detail panel where the CV (view/download) and the
      // shortlist/hire/reject dialogs live — so every status change captures
      // the interview date / start date and sends a complete candidate email.
      cell: (a) => (
        <div className="flex justify-end">
          <Button size="sm" variant="outline" onClick={() => viewDetail(a.id)}>Review</Button>
        </div>
      ),
    },
  ];

  return (
    <>
      {apps.loading ? (
        <TableSkeleton rows={5} cols={5} />
      ) : (
        <DataTable columns={cols} rows={apps.data ?? []} loading={false} empty="No applications yet." />
      )}
      <ApplicationDetailSlideOver
        open={openDetail}
        onOpenChange={setOpenDetail}
        applicationId={detailId}
        onChanged={apps.refresh}
      />
    </>
  );
}
