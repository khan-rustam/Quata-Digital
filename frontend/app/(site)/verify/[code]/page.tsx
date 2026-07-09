import type { Metadata } from "next";
import { BadgeCheck, XCircle, Building2, Briefcase, Hash } from "lucide-react";
import { apiUrl } from "@/lib/api";
import { Logo } from "@/components/site/logo";

export const metadata: Metadata = {
  title: "Employee verification — QUATA Digital",
  robots: { index: false, follow: false },
};

type Verify = {
  verified: boolean;
  full_name: string;
  employee_number: string;
  job_title: string | null;
  department: string | null;
  business_unit: string | null;
  avatar_url: string | null;
  employment_status: string;
};

async function fetchVerify(code: string): Promise<Verify | null> {
  try {
    const res = await fetch(`${apiUrl}/verify/${encodeURIComponent(code)}`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as Verify;
  } catch {
    return null;
  }
}

function initials(name: string): string {
  return name.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();
}

export default async function VerifyPage({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  const data = await fetchVerify(code);

  return (
    <div className="min-h-[70vh] flex items-center justify-center px-4 py-16">
      <div className="w-full max-w-md">
        <div className="flex justify-center mb-6">
          <Logo />
        </div>

        {!data ? (
          <div className="rounded-3xl border border-border bg-card p-8 text-center ring-soft">
            <XCircle className="h-12 w-12 text-rose-600 mx-auto" />
            <h1 className="mt-4 text-xl font-semibold">Verification failed</h1>
            <p className="mt-2 text-sm text-muted-foreground">
              This code doesn&apos;t match an active QUATA Digital employee. If you received an ID
              card that fails to verify, please contact{" "}
              <a href="mailto:support@quatadigital.com" className="text-primary">support@quatadigital.com</a>.
            </p>
          </div>
        ) : (
          <div className="rounded-3xl border border-border bg-card overflow-hidden ring-soft">
            <div className="bg-primary/10 px-6 py-4 flex items-center justify-center gap-2 text-primary">
              <BadgeCheck className="h-5 w-5" />
              <span className="text-sm font-semibold uppercase tracking-wider">Verified employee</span>
            </div>
            <div className="p-8 text-center">
              <div className="mx-auto h-24 w-24 rounded-full bg-brand-soft text-primary inline-flex items-center justify-center text-2xl font-bold overflow-hidden">
                {data.avatar_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={data.avatar_url} alt={data.full_name} className="h-full w-full object-cover" />
                ) : (
                  initials(data.full_name)
                )}
              </div>
              <h1 className="mt-4 text-xl font-semibold">{data.full_name}</h1>
              <div className="mt-1 inline-flex items-center gap-1.5 text-sm text-muted-foreground">
                <Hash className="h-3.5 w-3.5 text-primary" />
                <code>{data.employee_number}</code>
              </div>

              <dl className="mt-6 space-y-3 text-left">
                {data.job_title && (
                  <div className="flex items-center gap-3">
                    <Briefcase className="h-4 w-4 text-primary shrink-0" />
                    <dd className="text-sm">{data.job_title}</dd>
                  </div>
                )}
                {data.department && (
                  <div className="flex items-center gap-3">
                    <Building2 className="h-4 w-4 text-primary shrink-0" />
                    <dd className="text-sm">
                      {data.department}
                      {data.business_unit && <span className="text-muted-foreground"> · {data.business_unit}</span>}
                    </dd>
                  </div>
                )}
              </dl>

              <div className="mt-6 border-t border-border pt-4">
                <span
                  className={
                    "inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium " +
                    (data.employment_status === "Active"
                      ? "bg-emerald-500/10 text-emerald-700"
                      : "bg-muted text-muted-foreground")
                  }
                >
                  <span className="h-1.5 w-1.5 rounded-full bg-current" />
                  {data.employment_status} employee
                </span>
              </div>
            </div>
          </div>
        )}

        <p className="mt-6 text-center text-xs text-muted-foreground">
          Verified against the QUATA Digital employee directory.
        </p>
      </div>
    </div>
  );
}
