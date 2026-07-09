"use client";

import * as React from "react";
import { Pencil } from "lucide-react";
import { FormDialog } from "@/components/admin/form-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useApi, useApiAction } from "@/lib/use-api";
import { useToast } from "@/components/ui/toast";

export type EmployeeProfile = {
  id: number;
  phone: string | null;
  job_title: string | null;
  gender: string | null;
  date_of_birth: string | null;
  nationality: string | null;
  national_id: string | null;
  marital_status: string | null;
  blood_group: string | null;
  personal_email: string | null;
  address: string | null;
  emergency_contacts: { name?: string; relationship?: string; phone?: string }[];
  employment_type: string | null;
  grade: string | null;
  work_location: string | null;
  manager_id: number | null;
  manager_name: string | null;
  date_hired: string | null;
  confirmation_date: string | null;
  contract_expiry: string | null;
  probation_status: string | null;
  annual_leave_entitlement: number | null;
  education: string | null;
  skills: string[];
  languages: string[];
  certifications: string[];
  previous_employment: string | null;
  portfolio_url: string | null;
};

type StaffLite = { id: number; full_name: string };

function fmtDate(s: string | null): string {
  if (!s) return "—";
  const d = new Date(`${s}T00:00:00`);
  return isNaN(d.getTime()) ? s : d.toLocaleDateString(undefined, { dateStyle: "medium" });
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  const empty = value === null || value === undefined || value === "" || value === "—";
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</dt>
      <dd className={empty ? "text-sm text-muted-foreground" : "text-sm text-foreground/90"}>
        {empty ? "—" : value}
      </dd>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">{title}</h3>
      <dl className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-3">{children}</dl>
    </div>
  );
}

export function EmployeePersonnelFile({
  profile,
  onSaved,
}: {
  profile: EmployeeProfile;
  onSaved: () => void;
}) {
  const [open, setOpen] = React.useState(false);
  const staff = useApi<StaffLite[]>(open ? "/admin/staff" : null);
  const action = useApiAction();
  const toast = useToast();
  const p = profile;

  async function onSubmit(form: FormData) {
    const str = (k: string) => {
      const v = String(form.get(k) || "").trim();
      return v || null;
    };
    const csv = (k: string) =>
      String(form.get(k) || "").split(",").map((s) => s.trim()).filter(Boolean);
    const contacts = String(form.get("emergency_contacts") || "")
      .split("\n")
      .map((line) => {
        const [name, relationship, phone] = line.split(",").map((s) => s.trim());
        return name ? { name, relationship: relationship || "", phone: phone || "" } : null;
      })
      .filter(Boolean);

    const payload = {
      phone: str("phone"),
      job_title: str("job_title"),
      gender: str("gender"),
      date_of_birth: str("date_of_birth"),
      nationality: str("nationality"),
      national_id: str("national_id"),
      marital_status: str("marital_status"),
      blood_group: str("blood_group"),
      personal_email: str("personal_email"),
      address: str("address"),
      emergency_contacts: contacts,
      employment_type: str("employment_type"),
      grade: str("grade"),
      work_location: str("work_location"),
      manager_id: form.get("manager_id") ? Number(form.get("manager_id")) : null,
      date_hired: str("date_hired"),
      confirmation_date: str("confirmation_date"),
      contract_expiry: str("contract_expiry"),
      probation_status: str("probation_status"),
      annual_leave_entitlement: form.get("annual_leave_entitlement") ? Number(form.get("annual_leave_entitlement")) : null,
      education: str("education"),
      skills: csv("skills"),
      languages: csv("languages"),
      certifications: csv("certifications"),
      previous_employment: str("previous_employment"),
      portfolio_url: str("portfolio_url"),
    };
    try {
      await action(`/admin/staff/${p.id}/profile`, { method: "PATCH", body: JSON.stringify(payload) });
      toast.success("Profile updated");
      setOpen(false);
      onSaved();
    } catch (err) {
      toast.error("Couldn't save", err instanceof Error ? err.message : "Try again.");
    }
  }

  return (
    <div className="rounded-2xl border border-border bg-card p-6 ring-soft">
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-sm font-semibold text-foreground/90">Personnel file</h2>
        <Button size="sm" variant="outline" onClick={() => setOpen(true)}>
          <Pencil className="h-3.5 w-3.5" /> Edit profile
        </Button>
      </div>

      <div className="space-y-6">
        <Section title="Personal">
          <Field label="Gender" value={p.gender} />
          <Field label="Date of birth" value={p.date_of_birth ? fmtDate(p.date_of_birth) : "—"} />
          <Field label="Nationality" value={p.nationality} />
          <Field label="National ID / Passport" value={p.national_id} />
          <Field label="Marital status" value={p.marital_status} />
          <Field label="Blood group" value={p.blood_group} />
          <Field label="Personal email" value={p.personal_email} />
          <Field label="Address" value={p.address} />
          <Field
            label="Emergency contacts"
            value={
              p.emergency_contacts.length
                ? p.emergency_contacts.map((c) => `${c.name}${c.relationship ? ` (${c.relationship})` : ""}${c.phone ? ` · ${c.phone}` : ""}`).join("; ")
                : "—"
            }
          />
        </Section>

        <Section title="Employment">
          <Field label="Employment type" value={p.employment_type} />
          <Field label="Grade" value={p.grade} />
          <Field label="Work location" value={p.work_location} />
          <Field label="Reporting manager" value={p.manager_name} />
          <Field label="Date hired" value={p.date_hired ? fmtDate(p.date_hired) : "—"} />
          <Field label="Confirmation date" value={p.confirmation_date ? fmtDate(p.confirmation_date) : "—"} />
          <Field label="Contract expiry" value={p.contract_expiry ? fmtDate(p.contract_expiry) : "—"} />
          <Field label="Probation status" value={p.probation_status} />
        </Section>

        <Section title="Professional">
          <Field label="Skills" value={p.skills.length ? p.skills.join(", ") : "—"} />
          <Field label="Languages" value={p.languages.length ? p.languages.join(", ") : "—"} />
          <Field label="Certifications" value={p.certifications.length ? p.certifications.join(", ") : "—"} />
          <Field label="Portfolio" value={p.portfolio_url ? <a href={p.portfolio_url} target="_blank" rel="noreferrer" className="text-primary">Link</a> : "—"} />
          <Field label="Education" value={p.education} />
          <Field label="Previous employment" value={p.previous_employment} />
        </Section>
      </div>

      <FormDialog
        open={open}
        onOpenChange={setOpen}
        title="Edit personnel file"
        submitLabel="Save profile"
        size="xl"
        onSubmit={onSubmit}
      >
        <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Personal</div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="grid gap-1.5">
            <Label htmlFor="gender">Gender</Label>
            <Select id="gender" name="gender" defaultValue={p.gender ?? ""}>
              <option value="">—</option>
              <option>Male</option>
              <option>Female</option>
              <option>Other</option>
              <option>Prefer not to say</option>
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="date_of_birth">Date of birth</Label>
            <Input id="date_of_birth" name="date_of_birth" type="date" defaultValue={p.date_of_birth ?? ""} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="nationality">Nationality</Label>
            <Input id="nationality" name="nationality" defaultValue={p.nationality ?? ""} placeholder="Cameroonian" />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="national_id">National ID / Passport</Label>
            <Input id="national_id" name="national_id" defaultValue={p.national_id ?? ""} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="marital_status">Marital status</Label>
            <Select id="marital_status" name="marital_status" defaultValue={p.marital_status ?? ""}>
              <option value="">—</option>
              <option>Single</option>
              <option>Married</option>
              <option>Divorced</option>
              <option>Widowed</option>
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="blood_group">Blood group</Label>
            <Input id="blood_group" name="blood_group" defaultValue={p.blood_group ?? ""} placeholder="O+" />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="personal_email">Personal email</Label>
            <Input id="personal_email" name="personal_email" type="email" defaultValue={p.personal_email ?? ""} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="phone">Phone</Label>
            <Input id="phone" name="phone" defaultValue={p.phone ?? ""} />
          </div>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="address">Residential address</Label>
          <Textarea id="address" name="address" rows={2} defaultValue={p.address ?? ""} />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="emergency_contacts">Emergency contacts — one per line: Name, Relationship, Phone</Label>
          <Textarea
            id="emergency_contacts"
            name="emergency_contacts"
            rows={2}
            defaultValue={p.emergency_contacts.map((c) => [c.name, c.relationship, c.phone].filter(Boolean).join(", ")).join("\n")}
            placeholder="Jane Doe, Spouse, +237..."
          />
        </div>

        <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground pt-2">Employment</div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="grid gap-1.5">
            <Label htmlFor="job_title">Position / title</Label>
            <Input id="job_title" name="job_title" defaultValue={p.job_title ?? ""} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="employment_type">Employment type</Label>
            <Select id="employment_type" name="employment_type" defaultValue={p.employment_type ?? ""}>
              <option value="">—</option>
              <option>Full-time</option>
              <option>Part-time</option>
              <option>Contract</option>
              <option>Intern</option>
              <option>Consultant</option>
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="grade">Grade</Label>
            <Input id="grade" name="grade" defaultValue={p.grade ?? ""} placeholder="e.g. L3" />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="work_location">Work location</Label>
            <Input id="work_location" name="work_location" defaultValue={p.work_location ?? ""} placeholder="Bamenda office" />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="manager_id">Reporting manager</Label>
            <Select id="manager_id" name="manager_id" defaultValue={p.manager_id ?? ""}>
              <option value="">— None —</option>
              {(staff.data ?? []).filter((s) => s.id !== p.id).map((s) => (
                <option key={s.id} value={s.id}>{s.full_name}</option>
              ))}
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="probation_status">Probation status</Label>
            <Select id="probation_status" name="probation_status" defaultValue={p.probation_status ?? ""}>
              <option value="">—</option>
              <option value="probation">On probation</option>
              <option value="confirmed">Confirmed</option>
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="date_hired">Date hired</Label>
            <Input id="date_hired" name="date_hired" type="date" defaultValue={p.date_hired ?? ""} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="confirmation_date">Confirmation date</Label>
            <Input id="confirmation_date" name="confirmation_date" type="date" defaultValue={p.confirmation_date ?? ""} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="contract_expiry">Contract expiry</Label>
            <Input id="contract_expiry" name="contract_expiry" type="date" defaultValue={p.contract_expiry ?? ""} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="annual_leave_entitlement">Annual leave (days/yr)</Label>
            <Input id="annual_leave_entitlement" name="annual_leave_entitlement" type="number" min={0} defaultValue={p.annual_leave_entitlement ?? 18} />
          </div>
        </div>

        <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground pt-2">Professional</div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="grid gap-1.5">
            <Label htmlFor="skills">Skills (comma-separated)</Label>
            <Input id="skills" name="skills" defaultValue={p.skills.join(", ")} placeholder="Python, Sales, Excel" />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="languages">Languages (comma-separated)</Label>
            <Input id="languages" name="languages" defaultValue={p.languages.join(", ")} placeholder="English, French" />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="certifications">Certifications (comma-separated)</Label>
            <Input id="certifications" name="certifications" defaultValue={p.certifications.join(", ")} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="portfolio_url">Portfolio URL</Label>
            <Input id="portfolio_url" name="portfolio_url" defaultValue={p.portfolio_url ?? ""} placeholder="https://" />
          </div>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="education">Education</Label>
          <Textarea id="education" name="education" rows={2} defaultValue={p.education ?? ""} />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="previous_employment">Previous employment</Label>
          <Textarea id="previous_employment" name="previous_employment" rows={2} defaultValue={p.previous_employment ?? ""} />
        </div>
      </FormDialog>
    </div>
  );
}
