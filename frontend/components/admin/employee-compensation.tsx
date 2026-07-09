"use client";

import * as React from "react";
import { Plus, Trash2, Wallet, Lock, FileDown } from "lucide-react";
import { FormDialog } from "@/components/admin/form-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useApi, useApiAction } from "@/lib/use-api";
import { apiUrl } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/components/ui/toast";

type Salary = {
  id: number;
  effective_date: string | null;
  currency: string;
  basic_salary: number;
  allowances: number;
  bonus: number;
  overtime: number;
  tax: number;
  pension: number;
  insurance: number;
  loan_deduction: number;
  advance_deduction: number;
  payment_method: string | null;
  notes: string | null;
  gross: number;
  total_deductions: number;
  net: number;
  created_at: string;
};

function money(n: number, currency: string): string {
  return `${n.toLocaleString()} ${currency}`;
}
function fmt(s: string | null): string {
  if (!s) return "—";
  const d = new Date(`${s}T00:00:00`);
  return isNaN(d.getTime()) ? s : d.toLocaleDateString(undefined, { dateStyle: "medium" });
}

export function EmployeeCompensation({ staffId }: { staffId: number }) {
  const salary = useApi<Salary[]>(`/admin/staff/${staffId}/salary`);
  const action = useApiAction();
  const toast = useToast();
  const { token } = useAuth();
  const [open, setOpen] = React.useState(false);
  const [payslipBusy, setPayslipBusy] = React.useState<number | null>(null);

  async function downloadPayslip(recordId: number) {
    setPayslipBusy(recordId);
    try {
      const res = await fetch(`${apiUrl}/admin/staff/${staffId}/salary/${recordId}/payslip.pdf`, {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });
      if (!res.ok) throw new Error(`Failed (${res.status})`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `payslip-${recordId}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      toast.error("Couldn't generate payslip", err instanceof Error ? err.message : "Try again.");
    } finally {
      setPayslipBusy(null);
    }
  }

  async function onSubmit(form: FormData) {
    const num = (k: string) => Number(form.get(k) || 0);
    const payload = {
      effective_date: String(form.get("effective_date") || "").trim() || null,
      currency: String(form.get("currency") || "XAF"),
      basic_salary: num("basic_salary"),
      allowances: num("allowances"),
      bonus: num("bonus"),
      overtime: num("overtime"),
      tax: num("tax"),
      pension: num("pension"),
      insurance: num("insurance"),
      loan_deduction: num("loan_deduction"),
      advance_deduction: num("advance_deduction"),
      payment_method: String(form.get("payment_method") || "").trim() || null,
      notes: String(form.get("notes") || "").trim() || null,
    };
    try {
      await action(`/admin/staff/${staffId}/salary`, { method: "POST", body: JSON.stringify(payload) });
      toast.success("Salary record added");
      setOpen(false);
      salary.refresh();
    } catch (err) {
      toast.error("Couldn't save", err instanceof Error ? err.message : "Try again.");
    }
  }

  async function del(id: number) {
    try {
      await action(`/admin/staff/${staffId}/salary/${id}`, { method: "DELETE" });
      salary.refresh();
    } catch (err) {
      toast.error("Couldn't delete", err instanceof Error ? err.message : "Try again.");
    }
  }

  const rows = salary.data ?? [];

  return (
    <div className="rounded-2xl border border-border bg-card p-6 ring-soft">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-foreground/90">Compensation</h2>
          <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider text-muted-foreground">
            <Lock className="h-3 w-3" /> Admin only
          </span>
        </div>
        <Button size="sm" variant="outline" onClick={() => setOpen(true)}>
          <Plus className="h-3.5 w-3.5" /> Add salary
        </Button>
      </div>
      {rows.length === 0 ? (
        <div className="text-sm text-muted-foreground">No salary records. Payroll disbursement will link to QuataPay later.</div>
      ) : (
        <div className="space-y-3">
          {rows.map((s) => (
            <div key={s.id} className="rounded-xl border border-border p-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <Wallet className="h-4 w-4 text-primary" />
                    <span className="text-lg font-semibold tracking-tight">{money(s.net, s.currency)}</span>
                    <span className="text-[11px] uppercase tracking-wider text-muted-foreground">net</span>
                  </div>
                  <div className="text-[11px] text-muted-foreground">
                    Effective {fmt(s.effective_date)}
                    {s.payment_method ? ` · via ${s.payment_method}` : ""}
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => downloadPayslip(s.id)}
                    disabled={payslipBusy === s.id}
                  >
                    <FileDown className="h-3.5 w-3.5" /> {payslipBusy === s.id ? "…" : "Payslip"}
                  </Button>
                  <button type="button" onClick={() => del(s.id)} className="p-1.5 text-muted-foreground hover:text-rose-700" aria-label="Delete record">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
              <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-muted-foreground sm:grid-cols-3">
                <span>Basic: <span className="text-foreground/85">{s.basic_salary.toLocaleString()}</span></span>
                <span>Allowances: <span className="text-foreground/85">{s.allowances.toLocaleString()}</span></span>
                <span>Bonus/OT: <span className="text-foreground/85">{(s.bonus + s.overtime).toLocaleString()}</span></span>
                <span>Gross: <span className="text-foreground/85">{s.gross.toLocaleString()}</span></span>
                <span>Deductions: <span className="text-foreground/85">−{s.total_deductions.toLocaleString()}</span></span>
              </div>
              {s.notes && <div className="mt-1 whitespace-pre-line text-sm text-foreground/85">{s.notes}</div>}
            </div>
          ))}
        </div>
      )}

      <FormDialog open={open} onOpenChange={setOpen} title="Add salary record" submitLabel="Save" size="lg" onSubmit={onSubmit}>
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="grid gap-1.5">
            <Label htmlFor="effective_date">Effective date</Label>
            <Input id="effective_date" name="effective_date" type="date" />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="currency">Currency</Label>
            <Input id="currency" name="currency" defaultValue="XAF" />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="payment_method">Payment method</Label>
            <Select id="payment_method" name="payment_method" defaultValue="">
              <option value="">—</option>
              <option value="bank">Bank</option>
              <option value="quatapay">QuataPay</option>
              <option value="cash">Cash</option>
            </Select>
          </div>
        </div>
        <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Earnings</div>
        <div className="grid gap-3 sm:grid-cols-4">
          <div className="grid gap-1.5"><Label htmlFor="basic_salary">Basic</Label><Input id="basic_salary" name="basic_salary" type="number" min={0} defaultValue={0} /></div>
          <div className="grid gap-1.5"><Label htmlFor="allowances">Allowances</Label><Input id="allowances" name="allowances" type="number" min={0} defaultValue={0} /></div>
          <div className="grid gap-1.5"><Label htmlFor="bonus">Bonus</Label><Input id="bonus" name="bonus" type="number" min={0} defaultValue={0} /></div>
          <div className="grid gap-1.5"><Label htmlFor="overtime">Overtime</Label><Input id="overtime" name="overtime" type="number" min={0} defaultValue={0} /></div>
        </div>
        <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Deductions</div>
        <div className="grid gap-3 sm:grid-cols-5">
          <div className="grid gap-1.5"><Label htmlFor="tax">Tax</Label><Input id="tax" name="tax" type="number" min={0} defaultValue={0} /></div>
          <div className="grid gap-1.5"><Label htmlFor="pension">Pension</Label><Input id="pension" name="pension" type="number" min={0} defaultValue={0} /></div>
          <div className="grid gap-1.5"><Label htmlFor="insurance">Insurance</Label><Input id="insurance" name="insurance" type="number" min={0} defaultValue={0} /></div>
          <div className="grid gap-1.5"><Label htmlFor="loan_deduction">Loan</Label><Input id="loan_deduction" name="loan_deduction" type="number" min={0} defaultValue={0} /></div>
          <div className="grid gap-1.5"><Label htmlFor="advance_deduction">Advance</Label><Input id="advance_deduction" name="advance_deduction" type="number" min={0} defaultValue={0} /></div>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="notes">Notes</Label>
          <Textarea id="notes" name="notes" rows={2} />
        </div>
      </FormDialog>
    </div>
  );
}
