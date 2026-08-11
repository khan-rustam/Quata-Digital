"use client";

/**
 * QCP templates — grouped by the number they are bound to for life.
 *
 * Meta restricts numbers that send marketing on an authentication template,
 * so the binding between a template's category and its account is the whole
 * point of this system. The database already makes a violation
 * unrepresentable (`ck_whatsapp_templates_auth_only_on_verify`,
 * `ck_whatsapp_templates_marketing_never_on_verify` and
 * `ck_whatsapp_templates_verify_is_auth_only` — Quata Verify takes the
 * `authentication` category and nothing else, not even `utility`), which is
 * why this screen groups by account first: reading down a column tells you
 * what that number is allowed to emit.
 *
 * `misbound` should therefore always be false. It is rendered loudly anyway
 * — if a row ever comes back true, a constraint was dropped or the row
 * predates one, and that is the single thing an operator must not have to
 * infer.
 *
 * This screen is now the reason that defect existed in the first place.
 * Before it, `category` was operator-typed data inserted by hand, so a
 * utility template could quietly sit on the verification number. Here the
 * category is a fixed choice, the number it may sit on is derived from it
 * (`categoryAllowedOn`), and an impossible pairing is refused in the form
 * before it is ever sent — with the same sentence the database would have
 * refused it with. The CHECK constraint is the floor, not the fix.
 */

import * as React from "react";
import {
  AlertTriangle,
  Archive,
  CloudDownload,
  FileCheck2,
  Pencil,
  Plus,
  RefreshCw,
  ShieldAlert,
} from "lucide-react";
import { PageShell } from "@/components/admin/page-shell";
import { EmptyState } from "@/components/admin/empty-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import {
  QCP,
  useQcpWrite,
  type QcpRefusal,
  type QcpSyncResult,
  type QcpTemplateAlert,
} from "../api";
import {
  CATEGORIES,
  CATEGORY_STYLE,
  Loading,
  LoadError,
  Note,
  PurposeChip,
  QcpTabs,
  RefusalBanner,
  StatusBadge,
  TEMPLATE_STATUS_TONE,
  categoryAllowedOn,
  fmt,
  separationReason,
  type QcpOverview,
  type QcpTemplate,
} from "../shared";

type TemplateAccount = {
  slug: string;
  name: string;
  purpose: "authentication" | "engagement";
  is_active: boolean;
  display_phone: string | null;
};

type TemplatesResponse = {
  items: QcpTemplate[];
  accounts: TemplateAccount[];
  misbound_count: number;
};

export default function QcpTemplatesPage() {
  return (
    <PageShell
      title="QCP templates"
      description="Every Meta template, grouped by the number it is bound to. An authentication template belongs on Quata Verify and nowhere else; marketing can never live there. The database enforces both — this screen makes it impossible to try."
      requirePermission="settings:manage"
    >
      <QcpTabs />
      <Templates />
    </PageShell>
  );
}

function Templates() {
  const [category, setCategory] = React.useState("");
  const [status, setStatus] = React.useState("");
  const [editing, setEditing] = React.useState<QcpTemplate | "new" | null>(null);
  const [retiring, setRetiring] = React.useState<QcpTemplate | null>(null);
  const [syncing, setSyncing] = React.useState<TemplateAccount | null>(null);
  const [syncResult, setSyncResult] = React.useState<
    (QcpSyncResult & { account_name: string }) | null
  >(null);
  const [refusal, setRefusal] = React.useState<QcpRefusal | null>(null);

  const { write, busy } = useQcpWrite();
  const toast = useToast();

  const params = new URLSearchParams();
  if (category) params.set("category", category);
  if (status) params.set("status", status);
  const qs = params.toString();

  const { data, error, loading, refresh } = useApi<TemplatesResponse>(
    `${QCP.templates}${qs ? `?${qs}` : ""}`
  );
  // The registry gives the create form its product list. A template may also
  // be platform-owned (no product), so this is never required.
  const overview = useApi<QcpOverview>(QCP.overview);

  // Outstanding sync alerts, read off the audit log. Separate from the report
  // a sync produces, because the sync that found the problem may have been
  // run by someone else, days ago, in another session — and an alert nobody
  // saw is exactly how a re-classified template stays invisible.
  const alerts = useApi<{ items: QcpTemplateAlert[] }>(QCP.templateAlerts);

  /**
   * Sync is per number, because Meta's template list is a property of one
   * WABA. The result is kept on screen rather than toasted: a sync that finds
   * a re-classified template returns 200 with the alert in the body, and that
   * alert is the single most valuable thing this endpoint produces — it is
   * exactly how "Meta silently moved a utility template onto Verify" becomes
   * visible instead of staying a latent defect.
   */
  async function onSync() {
    if (!syncing) return;
    setRefusal(null);
    const account = syncing;
    const res = await write<QcpSyncResult>(QCP.templateSync(account.slug), {
      method: "POST",
    });
    setSyncing(null);
    if (!res.ok) {
      setRefusal(res.refusal);
      return;
    }
    setSyncResult({ ...res.data, account_name: account.name });
    alerts.refresh();
    const found = res.data.alerts?.length ?? 0;
    if (found > 0) {
      toast.error(
        `${found} alert${found === 1 ? "" : "s"} from Meta`,
        `${account.name}: Meta's view differs from ours. Read the alerts before enabling anything.`
      );
    } else {
      toast.success(
        `${account.name} synced`,
        `${res.data.created ?? 0} new, ${res.data.updated ?? 0} updated, ${
          res.data.unchanged ?? 0
        } unchanged.`
      );
    }
    refresh();
  }

  async function onRetire() {
    if (!retiring) return;
    const res = await write(QCP.templateRetire(retiring.id), { method: "POST" });
    setRetiring(null);
    if (!res.ok) {
      setRefusal(res.refusal);
      return;
    }
    toast.success("Template retired", `${retiring.name} can no longer be routed to.`);
    refresh();
  }

  if (loading && !data) return <Loading label="Loading templates…" />;
  if (error) return <LoadError error={error} onRetry={refresh} />;
  if (!data) return <Loading label="Loading templates…" />;

  const filtersActive = Boolean(category || status);

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <Select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="w-auto"
          aria-label="Filter by category"
        >
          <option value="">All categories</option>
          <option value="authentication">Authentication</option>
          <option value="utility">Utility</option>
          <option value="marketing">Marketing</option>
        </Select>
        <Select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="w-auto"
          aria-label="Filter by approval state"
        >
          <option value="">All approval states</option>
          <option value="draft">Draft</option>
          <option value="pending_approval">Pending approval</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
          <option value="paused">Paused</option>
          <option value="disabled">Disabled</option>
        </Select>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <Button variant="outline" size="sm" onClick={refresh}>
            <RefreshCw className="h-3.5 w-3.5" /> Refresh
          </Button>
          <Button
            size="sm"
            onClick={() => setEditing("new")}
            disabled={data.accounts.length === 0}
          >
            <Plus className="h-3.5 w-3.5" /> New template
          </Button>
        </div>
      </div>

      {refusal && <RefusalBanner refusal={refusal} onDismiss={() => setRefusal(null)} />}

      {syncResult && (
        <SyncReport result={syncResult} onDismiss={() => setSyncResult(null)} />
      )}

      {(alerts.data?.items?.length ?? 0) > 0 && (
        <div className="rounded-2xl border-2 border-rose-400 bg-rose-50 p-4 text-rose-900">
          <div className="flex items-start gap-2">
            <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
            <div className="min-w-0">
              <div className="text-sm font-semibold">
                {alerts.data!.items.length} outstanding sync alert
                {alerts.data!.items.length === 1 ? "" : "s"}
              </div>
              <p className="mt-0.5 text-xs">
                Meta&apos;s view of a template differs from ours. Each of these is a
                template that cannot send, or should not — resolve them before enabling
                anything.
              </p>
              <ul className="mt-2 grid gap-1.5 text-xs">
                {alerts.data!.items.map((a, i) => (
                  <li key={i} className="break-words">
                    <strong>{String(a.template ?? a.kind ?? a.code ?? "template")}</strong>
                    {a.account ? ` on ${String(a.account)}` : ""}
                    {a.detail ? ` — ${String(a.detail)}` : ""}
                    {a.created_at ? ` (${fmt(String(a.created_at))})` : ""}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {data.misbound_count > 0 && (
        <div className="rounded-2xl border-2 border-rose-400 bg-rose-50 p-4 text-rose-900">
          <div className="flex items-start gap-2">
            <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <div className="text-sm font-semibold">
                {data.misbound_count} template
                {data.misbound_count === 1 ? " is" : "s are"} on the wrong number
              </div>
              <p className="mt-1 text-xs">
                This should be impossible — the database forbids it. Either a CHECK
                constraint was dropped, these rows predate it, or Meta re-classified a
                template during a sync. Meta will restrict the number before it sends.
                Do not enable delivery until this is resolved: retire each row below, or
                recreate it on the other number.
              </p>
            </div>
          </div>
        </div>
      )}

      {data.accounts.length === 0 ? (
        <EmptyState
          icon={FileCheck2}
          title="No accounts registered"
          description="Templates are bound to a number, and no number exists yet. There is nothing to create a template against."
        />
      ) : (
        data.accounts.map((account) => {
          const rows = data.items.filter((t) => t.account === account.slug);
          return (
            <section key={account.slug}>
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-sm font-semibold tracking-tight">{account.name}</h3>
                <PurposeChip purpose={account.purpose} />
                <Badge variant={account.is_active ? "success" : "default"}>
                  {account.is_active ? "Active" : "Inactive"}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  {account.display_phone ?? "no number set"} · {rows.length} template
                  {rows.length === 1 ? "" : "s"}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  className="ml-auto"
                  onClick={() => setSyncing(account)}
                  disabled={busy}
                >
                  <CloudDownload className="h-3.5 w-3.5" /> Sync from Meta
                </Button>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                {account.purpose === "authentication"
                  ? "Allowed here: authentication only. Utility and marketing are refused by the storage engine."
                  : "Allowed here: marketing and utility. Authentication is refused by the storage engine."}
              </p>

              <div className="mt-3">
                {rows.length === 0 ? (
                  <EmptyState
                    icon={FileCheck2}
                    title={
                      filtersActive
                        ? "No templates match these filters on this number"
                        : "No templates on this number yet"
                    }
                    description={
                      filtersActive
                        ? "Clear the filters above to see everything bound to this number."
                        : "Nothing has been registered here. Create one, or sync from Meta if templates already exist on the WABA."
                    }
                  />
                ) : (
                  <div className="overflow-hidden rounded-2xl border border-border bg-card ring-soft divide-y divide-border">
                    {rows.map((t) => (
                      <TemplateRow
                        key={t.id}
                        template={t}
                        onEdit={() => setEditing(t)}
                        onRetire={() => setRetiring(t)}
                      />
                    ))}
                  </div>
                )}
              </div>
            </section>
          );
        })
      )}

      {data.items.length === 0 && !filtersActive && (
        <Note>
          No templates anywhere is the expected state on a fresh install. QCP has never
          submitted anything to Meta, so there is nothing to approve.
        </Note>
      )}

      {/* Keyed so the form is a fresh mount per row — its category/number
          state is derived from the template it opened on. */}
      {editing !== null && (
        <TemplateDialog
          key={editing === "new" ? "new" : editing.id}
          template={editing === "new" ? null : editing}
          accounts={data.accounts}
          products={overview.data?.products ?? []}
          onClose={() => setEditing(null)}
          onSaved={refresh}
        />
      )}

      <ConfirmDialog
        open={!!syncing}
        onOpenChange={(v) => !v && setSyncing(null)}
        title={`Sync ${syncing?.name ?? "this number"} from Meta?`}
        description="Pulls the current name, language, category and approval state for every template on this WABA. Meta is the authority on category — if it has re-classified one of yours to MARKETING, this is how you find out, and the row is quarantined so nothing can route to it. No message is sent to anyone."
        confirmLabel="Sync now"
        onConfirm={onSync}
      />

      <ConfirmDialog
        open={!!retiring}
        onOpenChange={(v) => !v && setRetiring(null)}
        title={`Retire ${retiring?.name ?? "template"}?`}
        description="The template stops being routable: any rule pointing at it will fail its guard rather than send. It is not deleted at Meta and the row stays for audit. Reversible by editing it back to draft."
        confirmLabel="Retire"
        destructive
        onConfirm={onRetire}
      />
    </div>
  );
}

/**
 * What Meta just said.
 *
 * A sync returns 200 even when it found something wrong, because the database
 * refusing a row *is* the successful outcome — the row was quarantined and the
 * separation held. That means the alerts cannot be surfaced by an error path;
 * they have to be read out of a successful body, which is what this does.
 */
function SyncReport({
  result,
  onDismiss,
}: {
  result: QcpSyncResult & { account_name: string };
  onDismiss: () => void;
}) {
  const alerts = result.alerts ?? [];
  return (
    <div
      className={cn(
        "rounded-2xl border p-4",
        alerts.length
          ? "border-2 border-rose-400 bg-rose-50 text-rose-900"
          : "border-emerald-200 bg-emerald-50 text-emerald-900"
      )}
    >
      <div className="flex items-start gap-2">
        {alerts.length ? (
          <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
        ) : (
          <CloudDownload className="mt-0.5 h-4 w-4 shrink-0" />
        )}
        <div className="min-w-0">
          <div className="text-sm font-semibold">
            {result.account_name}: {result.fetched ?? 0} template
            {result.fetched === 1 ? "" : "s"} from Meta
          </div>
          <p className="mt-0.5 text-xs">
            {result.created ?? 0} new · {result.updated ?? 0} updated ·{" "}
            {result.unchanged ?? 0} unchanged
            {alerts.length === 0 && " · nothing Meta says contradicts what we hold"}
          </p>
          {alerts.length > 0 && (
            <ul className="mt-2 grid gap-1.5 text-xs">
              {alerts.map((a, i) => (
                <li key={i} className="break-words">
                  <strong>{String(a.template ?? a.kind ?? a.code ?? "template")}</strong>
                  {a.detail ? ` — ${String(a.detail)}` : ""}
                </li>
              ))}
            </ul>
          )}
        </div>
        <button
          type="button"
          onClick={onDismiss}
          className="ml-auto shrink-0 text-[11px] underline"
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}

function TemplateRow({
  template: t,
  onEdit,
  onRetire,
}: {
  template: QcpTemplate;
  onEdit: () => void;
  onRetire: () => void;
}) {
  return (
    <div className={cn("p-4", t.misbound && "bg-rose-50")}>
      <div className="flex flex-wrap items-center gap-2">
        {t.misbound && (
          <span className="inline-flex items-center gap-1 rounded-full border-2 border-rose-500 bg-rose-100 px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide text-rose-900">
            <AlertTriangle className="h-3 w-3" /> Wrong number
          </span>
        )}
        <span className="text-sm font-medium">{t.name}</span>
        <Badge variant="outline" className={CATEGORY_STYLE[t.category]}>
          {t.category}
        </Badge>
        <StatusBadge value={t.status} tones={TEMPLATE_STATUS_TONE} />
        <Badge variant="outline" className="text-[11px]">
          {t.language}
        </Badge>
        {t.product && (
          <Badge variant="outline" className="text-[11px]">
            {t.product}
          </Badge>
        )}
        <span className="ml-auto text-xs text-muted-foreground">
          synced {fmt(t.last_synced_at)}
        </span>
        <div className="flex items-center gap-1">
          <Button size="sm" variant="ghost" onClick={onEdit} aria-label={`Edit ${t.name}`}>
            <Pencil className="h-3.5 w-3.5" />
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="text-rose-700"
            onClick={onRetire}
            aria-label={`Retire ${t.name}`}
          >
            <Archive className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      <div className="mt-1.5 text-xs text-muted-foreground">
        intent <code>{t.intent}</code>
        {t.variables.length > 0 && ` · ${t.variables.length} variable(s): ${t.variables.join(", ")}`}
        {t.provider_template_id && ` · Meta id ${t.provider_template_id}`}
      </div>

      {t.misbound && (
        <p className="mt-2 text-xs font-medium text-rose-800">
          This template&apos;s category is <strong>{t.category}</strong>, but it is bound
          to the <strong>{t.account_purpose}</strong> number. Meta enforces this
          separation at the account level — sending it would put the number at risk.
        </p>
      )}
      {t.rejection_reason && (
        <p className="mt-2 text-xs text-rose-700 break-words">
          Rejected by Meta: {t.rejection_reason}
        </p>
      )}
    </div>
  );
}

/* ----------------------------------------------------------- create/edit */

/**
 * The form that closed the original defect.
 *
 * `category` used to be free text an engineer typed into an INSERT. Here it
 * is one of three fixed values, and the set of numbers it may be bound to is
 * *derived* from it rather than chosen independently — an account that cannot
 * legally hold the selected category is not offered. If a pairing is somehow
 * still assembled (an edit that changes the category of an existing row), the
 * form refuses it with the same sentence the database would, before any
 * request is made.
 */
function TemplateDialog({
  template,
  accounts,
  products,
  onClose,
  onSaved,
}: {
  template: QcpTemplate | null;
  accounts: TemplateAccount[];
  products: { slug: string; name: string }[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const { write, busy } = useQcpWrite();
  const toast = useToast();
  const [category, setCategory] = React.useState<string>(
    template?.category ?? "utility"
  );
  const [accountSlug, setAccountSlug] = React.useState<string>(
    template?.account ?? ""
  );
  const [refusal, setRefusal] = React.useState<QcpRefusal | null>(null);

  // Meta owns the category the moment it has seen the template. After that
  // the local value is a record of Meta's decision, and editing it here would
  // let someone paper over a re-classification instead of acting on it.
  const categoryEditable = !template || template.status === "draft";

  const eligible = accounts.filter((a) => categoryAllowedOn(category, a.purpose));
  const selected = accounts.find((a) => a.slug === accountSlug) ?? null;
  const violation = selected ? separationReason(category, selected.purpose) : null;

  // Changing the category can strand the selected account. Say so rather than
  // silently reassigning it — the operator has to see the pairing change.
  const stranded = Boolean(accountSlug && !selected) || Boolean(violation);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setRefusal(null);
    const form = new FormData(e.currentTarget);
    const str = (k: string) => String(form.get(k) ?? "").trim();

    if (!selected) {
      setRefusal({
        title: "Pick a number",
        detail:
          "A template is bound to exactly one number for its whole life. Choose the one this category belongs on.",
        policy: true,
      });
      return;
    }
    const reason = separationReason(category, selected.purpose);
    if (reason) {
      setRefusal({
        title: "Refused — wrong number for that category",
        detail: `${reason} Nothing was sent to QCP.`,
        policy: true,
      });
      return;
    }

    // Create and update take different shapes on purpose: `name`, `language`
    // and `account` are immutable once a template exists, and `category` is
    // only editable while Meta has never seen the row. The form mirrors that
    // rather than sending fields the model forbids.
    const res = template
      ? await write<{ warnings?: { code: string; detail: string }[] }>(QCP.template(template.id), {
          method: "PATCH",
          body: {
            intent: str("intent"),
            body: str("body"),
            product: str("product") || null,
            ...(categoryEditable ? { category } : {}),
          },
        })
      : await write<{ warnings?: { code: string; detail: string }[] }>(QCP.templates, {
          method: "POST",
          body: {
            account: selected.slug,
            name: str("name"),
            language: str("language") || "en",
            category,
            intent: str("intent"),
            body: str("body"),
            product: str("product") || null,
          },
        });

    if (!res.ok) {
      setRefusal(res.refusal);
      return;
    }
    // The write can succeed *and* still have something to say. A body that
    // reads like a verification code on a non-authentication template is
    // refused outright when it is unambiguous, and allowed with a `warnings`
    // entry when it is not — that is deliberately the "warn where you cannot
    // be certain" half of the rule, and swallowing it here would make the
    // ambiguous half invisible to the only person who can judge it.
    const warnings = res.data?.warnings ?? [];
    if (warnings.length > 0) {
      // No `warning` kind on this toast component; `info` is the closest
      // that does not read as a failed write, and the title carries the weight.
      toast.info(
        template ? "Template updated — check the body" : "Template created — check the body",
        warnings[0].detail
      );
    } else {
      toast.success(
        template ? "Template updated" : "Template created",
        template
          ? `${template.name} on ${selected.name}.`
          : `${str("name")} · ${category} on ${selected.name}. It stays a draft until a sync finds Meta approving it.`
      );
    }
    onSaved();
    onClose();
  }

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{template ? `Edit ${template.name}` : "New template"}</DialogTitle>
          <DialogDescription>
            A template&apos;s category decides which number it may live on, and that
            binding is permanent. Creating it here does not submit it to Meta and does
            not send anything.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={submit} className="grid gap-4 max-h-[70vh] overflow-y-auto pr-1">
          {refusal && (
            <RefusalBanner refusal={refusal} onDismiss={() => setRefusal(null)} />
          )}

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="name">Template name *</Label>
              <Input
                id="name"
                name="name"
                required={!template}
                disabled={!!template}
                defaultValue={template?.name ?? ""}
                placeholder="otp_login_code"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="language">Language *</Label>
              <Input
                id="language"
                name="language"
                required={!template}
                disabled={!!template}
                defaultValue={template?.language ?? "en"}
                placeholder="en"
              />
            </div>
          </div>
          {template && (
            <p className="-mt-2 text-[11px] text-muted-foreground">
              Name, language and number identify the template at Meta and cannot be
              changed. To move any of them, retire this one and create a new one.
            </p>
          )}

          {/* --- the pairing, as one unit, because it is one decision --- */}
          <fieldset className="grid gap-3 rounded-xl border border-border bg-surface-soft p-3.5">
            <legend className="px-1 text-xs font-semibold">
              Category and number — the pairing Meta enforces
            </legend>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="category">Meta category *</Label>
                <Select
                  id="category"
                  value={category}
                  disabled={!categoryEditable}
                  onChange={(e) => setCategory(e.target.value)}
                >
                  {CATEGORIES.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </Select>
                {!categoryEditable && (
                  <p className="text-[11px] text-muted-foreground">
                    Meta has seen this template, so Meta owns its category. If it has
                    been re-classified, sync and act on the alert — do not overwrite the
                    record of what Meta decided.
                  </p>
                )}
              </div>
              <div className="grid gap-2">
                <Label htmlFor="account">Number *</Label>
                <Select
                  id="account"
                  value={accountSlug}
                  disabled={!!template}
                  onChange={(e) => setAccountSlug(e.target.value)}
                >
                  <option value="">— Choose —</option>
                  {eligible.map((a) => (
                    <option key={a.slug} value={a.slug}>
                      {a.name} ({a.purpose})
                    </option>
                  ))}
                  {/* Keep a now-illegal selection visible and disabled rather
                      than silently snapping to another number — the operator
                      has to see which pairing broke. */}
                  {selected && violation && (
                    <option value={selected.slug} disabled>
                      {selected.name} — not allowed for {category}
                    </option>
                  )}
                </Select>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2 text-xs">
              <Badge variant="outline" className={CATEGORY_STYLE[category]}>
                {category}
              </Badge>
              <span className="text-muted-foreground">may only live on</span>
              {eligible.length === 0 ? (
                <Badge variant="danger">no registered number</Badge>
              ) : (
                eligible.map((a) => (
                  <Badge key={a.slug} variant="outline">
                    {a.name}
                  </Badge>
                ))
              )}
            </div>

            {stranded && (
              <div className="rounded-lg border-2 border-rose-400 bg-rose-50 p-3 text-xs text-rose-900">
                <div className="flex items-start gap-2">
                  <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  <span>
                    {violation ??
                      "Changing the category unbound the number you had chosen — that pairing is not allowed. Pick a number from the list above."}
                  </span>
                </div>
              </div>
            )}

            {category === "authentication" ? (
              <p className="text-[11px] text-muted-foreground">
                Authentication templates carry security codes and live on Quata Verify
                alone. That number takes nothing else — not even utility.
              </p>
            ) : (
              <p className="text-[11px] text-muted-foreground">
                Utility and marketing live on QUATA. Putting either on Quata Verify is
                what gets Quata Verify restricted — and every login code in the fleet
                goes out from that number.
              </p>
            )}
          </fieldset>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="intent">Intent *</Label>
              <Input
                id="intent"
                name="intent"
                required
                defaultValue={template?.intent ?? ""}
                placeholder="login_otp"
              />
              <p className="text-[11px] text-muted-foreground">
                What a product asks for. Routing rules match on this.
              </p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="product">Owning product</Label>
              <Select id="product" name="product" defaultValue={template?.product ?? ""}>
                <option value="">— Platform-owned —</option>
                {products.map((p) => (
                  <option key={p.slug} value={p.slug}>
                    {p.name}
                  </option>
                ))}
              </Select>
            </div>
          </div>

          <div className="grid gap-2">
            <Label htmlFor="body">Body *</Label>
            <Textarea
              id="body"
              name="body"
              rows={3}
              required
              placeholder="Your {{1}} code is {{2}}. It expires in {{3}} minutes."
            />
            <p className="text-[11px] text-muted-foreground">
              QCP derives the variables from the <code>{"{{n}}"}</code> placeholders and
              stores the body as a hash so it can tell when Meta&apos;s copy has drifted.
              Never put a real code or any customer data in it.
              {template && template.variables.length > 0 && (
                <>
                  {" "}
                  Currently {template.variables.length} variable(s):{" "}
                  {template.variables.join(", ")}.
                </>
              )}
            </p>
          </div>

          <DialogFooter className="pt-2">
            <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
              Cancel
            </Button>
            <Button type="submit" disabled={busy || stranded || !accountSlug}>
              {template ? "Save changes" : "Create template"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
