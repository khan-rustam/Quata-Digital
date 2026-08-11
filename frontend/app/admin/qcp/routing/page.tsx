"use client";

/**
 * QCP routing — product + intent + locale → the template that answers it.
 *
 * This is the table the sender walks. A product asks QCP for an intent
 * ("login_otp"); routing decides which number that goes out on and which
 * approved template carries it. Every guard failure a product will ever see
 * originates here, and until now those failures were only visible after the
 * fact, as a suppression row on the overview with a machine-written reason.
 *
 * So this screen's real job is not the list — it is the **Problems** panel.
 * It evaluates, before anything is sent, the three ways a rule set can be
 * wrong:
 *
 *   * an enabled product with no active rule at all, or an intent with no
 *     rule, so every call is refused;
 *   * a rule pointing at a template Meta has not approved (or that does not
 *     exist), so the send fails its guard;
 *   * a rule aimed at a number the product is not allowed to reach, or at a
 *     purpose whose template category does not belong there.
 *
 * The evaluation is done in the console, from the rules, templates and
 * products already on screen, and it mirrors the guards the backend runs. It
 * is an early warning, never an authority: QCP re-runs every one of these
 * when a rule is activated and refuses there if they do not hold. That is
 * also why activation is its own route rather than a checkbox in the form —
 * the guards have to run against the world as it is at that moment, not as it
 * was when somebody typed the rule.
 */

import * as React from "react";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
  Waypoints,
} from "lucide-react";
import { PageShell } from "@/components/admin/page-shell";
import { EmptyState } from "@/components/admin/empty-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
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
  type QcpRoutingResponse,
  type QcpRoutingRule,
  type QcpRuleProblem,
} from "../api";

import {
  Loading,
  LoadError,
  Note,
  PurposeBadge,
  QcpTabs,
  RefusalBanner,
  categoryAllowedOn,
  type QcpOverview,
  type QcpProduct,
  type QcpTemplate,
} from "../shared";

type TemplatesResponse = { items: QcpTemplate[] };

/**
 * A routing problem as this screen states it.
 *
 * The backend emits `{code, severity, detail}` alongside a write and a set of
 * named lists from `/coverage`. Both are normalised into this so the panel
 * below renders one thing, and so a problem always knows which rule it is
 * about.
 */
type RoutingProblem = {
  kind: string;
  rule_id: number | null;
  product: string | null;
  intent: string | null;
  message: string;
};

export default function QcpRoutingPage() {
  return (
    <PageShell
      title="QCP routing"
      description="What a product's intent resolves to: which number it goes out on, and which approved template carries it. A send with no matching rule is refused before Meta is contacted — this is where that is prevented rather than diagnosed."
      requirePermission="settings:manage"
    >
      <QcpTabs />
      <Routing />
    </PageShell>
  );
}

function Routing() {
  const rules = useApi<QcpRoutingResponse>(QCP.routingRules);
  const overview = useApi<QcpOverview>(QCP.overview);
  const templates = useApi<TemplatesResponse>(QCP.templates);

  const { write, busy } = useQcpWrite();
  const toast = useToast();
  const [editing, setEditing] = React.useState<QcpRoutingRule | "new" | null>(null);
  const [deleting, setDeleting] = React.useState<QcpRoutingRule | null>(null);
  const [refusal, setRefusal] = React.useState<QcpRefusal | null>(null);

  function refreshAll() {
    rules.refresh();
    overview.refresh();
    templates.refresh();
  }

  /**
   * Activation is its own route because it is its own decision: the backend
   * re-runs every guard at that moment, since the world has moved since the
   * rule was written. Deactivation is never refused — stopping traffic has to
   * work unconditionally.
   */
  async function onToggleActive(rule: QcpRoutingRule) {
    setRefusal(null);
    const res = await write<{ problems?: { detail?: string }[] }>(
      rule.is_active
        ? QCP.routingRuleDeactivate(rule.id)
        : QCP.routingRuleActivate(rule.id),
      { method: "POST" }
    );
    if (!res.ok) {
      setRefusal(res.refusal);
      return;
    }
    const warnings = res.data?.problems ?? [];
    if (!rule.is_active && warnings.length > 0) {
      toast.info(
        `${rule.intent} is active, with ${warnings.length} warning${
          warnings.length === 1 ? "" : "s"
        }`,
        warnings[0]?.detail ?? "It is live but may not send today."
      );
    } else {
      toast.success(
        rule.is_active ? `${rule.intent} deactivated` : `${rule.intent} activated`,
        rule.is_active
          ? "The sender now ignores this rule entirely."
          : "The sender will use this rule for that intent."
      );
    }
    refreshAll();
  }

  async function onDelete() {
    if (!deleting) return;
    const res = await write(QCP.routingRule(deleting.id), { method: "DELETE" });
    setDeleting(null);
    if (!res.ok) {
      setRefusal(res.refusal);
      return;
    }
    toast.success(
      "Rule deleted",
      `${deleting.product ?? "platform"} · ${deleting.intent} no longer resolves to anything.`
    );
    refreshAll();
  }

  if (rules.loading && !rules.data) return <Loading label="Loading routing rules…" />;
  if (rules.error) return <LoadError error={rules.error} onRetry={refreshAll} />;
  if (!rules.data) return <Loading label="Loading routing rules…" />;

  const items = rules.data.items ?? [];
  const products = overview.data?.products ?? [];
  const allTemplates = templates.data?.items ?? [];
  const problems = evaluateProblems(items, products, allTemplates);

  const byProduct = new Map<string, QcpRoutingRule[]>();
  for (const r of items) {
    const key = r.product ?? "";
    byProduct.set(key, [...(byProduct.get(key) ?? []), r]);
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="outline" size="sm" onClick={refreshAll}>
          <RefreshCw className="h-3.5 w-3.5" /> Refresh
        </Button>
        <Button
          size="sm"
          className="ml-auto"
          onClick={() => setEditing("new")}
          disabled={products.length === 0}
          title={
            products.length === 0
              ? "Register a product on the Registry tab first — a rule belongs to one."
              : undefined
          }
        >
          <Plus className="h-3.5 w-3.5" /> New rule
        </Button>
      </div>

      {refusal && <RefusalBanner refusal={refusal} onDismiss={() => setRefusal(null)} />}

      <Problems problems={problems} />

      {items.length === 0 ? (
        <div className="grid gap-3">
          <EmptyState
            icon={Waypoints}
            title="No routing rules"
            description="Nothing resolves to anything yet. With every product disabled that is the correct state — nothing is asking. A rule is needed before the first product migrates."
            action={
              products.length > 0 ? (
                <Button onClick={() => setEditing("new")}>
                  <Plus className="h-4 w-4" /> New rule
                </Button>
              ) : undefined
            }
          />
          <Note>
            A rule is the only thing that turns &ldquo;QuataPay wants to send
            login_otp&rdquo; into &ldquo;send template <code>otp_login_code</code> from
            Quata Verify&rdquo;. Without one, that call is refused with a reason rather
            than guessed at.
          </Note>
        </div>
      ) : (
        [...byProduct.entries()].map(([slug, rows]) => {
          const product = products.find((p) => p.slug === slug) ?? null;
          return (
            <section key={slug || "__platform__"}>
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-sm font-semibold tracking-tight">
                  {product?.name ?? slug ?? "Unknown product"}
                </h3>
                {product && (
                  <Badge variant={product.is_enabled ? "success" : "default"}>
                    {product.is_enabled ? "Enabled" : "Disabled"}
                  </Badge>
                )}
                <span className="text-xs text-muted-foreground">
                  {/* `is_effectively_live`, not `is_active`: a rule whose
                      product lost the purpose it routes to is switched on and
                      carries nothing. Counting it as active is how someone
                      concludes the OTP path is up when it is not. */}
                  {rows.filter((r) => r.is_effectively_live).length} live of {rows.length}
                </span>
              </div>
              <div className="mt-3 overflow-hidden rounded-2xl border border-border bg-card ring-soft divide-y divide-border">
                {[...rows]
                  .sort((a, b) => a.priority - b.priority || a.intent.localeCompare(b.intent))
                  .map((r) => (
                    <RuleRow
                      key={r.id}
                      rule={r}
                      problems={problems.filter((p) => p.rule_id === r.id)}
                      busy={busy}
                      onEdit={() => setEditing(r)}
                      onDelete={() => setDeleting(r)}
                      onToggle={() => onToggleActive(r)}
                    />
                  ))}
              </div>
            </section>
          );
        })
      )}

      {/* Keyed so the form mounts fresh per rule rather than resetting itself
          in an effect. */}
      {editing !== null && (
        <RuleDialog
          key={editing === "new" ? "new" : editing.id}
          rule={editing === "new" ? null : editing}
          products={products}
          templates={allTemplates}
          onClose={() => setEditing(null)}
          onSaved={refreshAll}
        />
      )}

      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(v) => !v && setDeleting(null)}
        title={`Delete the rule for ${deleting?.intent ?? "this intent"}?`}
        description="Any product call for that intent will be refused with 'no rule' from the moment this is gone. Deactivating the rule instead has the same routing effect but keeps the row."
        confirmLabel="Delete rule"
        destructive
        onConfirm={onDelete}
      />

      {busy && <Loading label="Applying…" />}
    </div>
  );
}

/* --------------------------------------------------------------- problems */

/**
 * The guard failures a product would hit, stated before it hits them.
 *
 * These mirror the checks the sender makes at send time. They are worded as
 * problems with a fix, not as the error strings the sender emits, because the
 * point of showing them here is that nobody has to read a suppression reason
 * out of a log to understand what is wrong.
 */
function evaluateProblems(
  rules: QcpRoutingRule[],
  products: QcpProduct[],
  templates: QcpTemplate[]
): RoutingProblem[] {
  const out: RoutingProblem[] = [];

  for (const p of products) {
    if (!p.is_enabled) continue;
    const mine = rules.filter((r) => r.product === p.slug);
    if (mine.length === 0 || mine.every((r) => !r.is_active)) {
      out.push({
        kind: "no_active_rule",
        rule_id: null,
        product: p.slug,
        intent: null,
        message: `${p.name} is enabled but has no active routing rule. Every intent it asks for will be refused with "no rule for that intent" before Meta is contacted.`,
      });
    }
  }

  for (const r of rules) {
    const product = products.find((p) => p.slug === r.product) ?? null;

    if (product && !(product.allowed_purposes ?? []).includes(r.purpose)) {
      out.push({
        kind: "purpose_not_granted",
        rule_id: r.id,
        product: r.product,
        intent: r.intent,
        message: `${product.name} is not allowed to reach the ${r.purpose} number, but this rule sends ${r.intent} there. Grant the purpose on the Registry tab, or route this intent to the other number.`,
      });
    }

    const candidates = templates.filter(
      (t) =>
        t.intent === r.template_intent &&
        t.account_purpose === r.purpose &&
        (!r.locale || t.language === r.locale)
    );

    if (candidates.length === 0) {
      const wrongNumber = templates.filter((t) => t.intent === r.template_intent);
      out.push({
        kind: "no_template",
        rule_id: r.id,
        product: r.product,
        intent: r.intent,
        message: wrongNumber.length
          ? `No template named "${r.template_intent}" exists on the ${r.purpose} number${
              r.locale ? ` in ${r.locale}` : ""
            }. There ${wrongNumber.length === 1 ? "is one" : `are ${wrongNumber.length}`} on the other number — a template cannot be moved, so create one here or route to that number.`
          : `No template with intent "${r.template_intent}" exists at all. Create it on the Templates tab before this rule can resolve.`,
      });
      continue;
    }

    if (!candidates.some((t) => t.status === "approved")) {
      const states = [...new Set(candidates.map((t) => t.status))].join(", ");
      out.push({
        kind: "unapproved_template",
        rule_id: r.id,
        product: r.product,
        intent: r.intent,
        message: `The template "${r.template_intent}" this rule points at is not approved by Meta (currently ${states.replace(/_/g, " ")}). Sends will fail their guard until it is. Sync from Meta on the Templates tab to pick up a newer decision.`,
      });
    }

    const misbound = candidates.find(
      (t) => !categoryAllowedOn(t.category, t.account_purpose)
    );
    if (misbound) {
      out.push({
        kind: "misbound_template",
        rule_id: r.id,
        product: r.product,
        intent: r.intent,
        message: `This rule resolves to "${misbound.name}", which is a ${misbound.category} template sitting on the ${misbound.account_purpose} number. That pairing should be impossible — do not activate this rule; resolve the template first.`,
      });
    }
  }

  return out;
}

function Problems({ problems }: { problems: RoutingProblem[] }) {
  if (problems.length === 0) {
    return (
      <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-emerald-900">
        <div className="flex items-start gap-2">
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
          <div className="text-sm">
            <span className="font-semibold">No routing problems.</span> Every enabled
            product has an active rule, and every rule resolves to an approved template
            on a number that product may reach.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border-2 border-amber-300 bg-amber-50 p-4 text-amber-900">
      <div className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
        <div className="min-w-0">
          <div className="text-sm font-semibold">
            {problems.length} routing problem{problems.length === 1 ? "" : "s"}
          </div>
          <p className="mt-0.5 text-[11px]">
            Evaluated in this console from the rules, templates and products on screen,
            mirroring the guards QCP runs at send time. QCP is the authority — it
            re-runs every one of these when a rule is activated, and will refuse there
            too.
          </p>
          <ul className="mt-2 grid gap-1.5 text-xs">
            {problems.map((p, i) => (
              <li key={`${p.kind}-${p.rule_id ?? "none"}-${i}`} className="flex gap-2">
                <Badge variant="outline" className="h-fit shrink-0 text-[10px]">
                  {p.kind.replace(/_/g, " ")}
                </Badge>
                <span className="break-words">{p.message}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------- rows */

function RuleRow({
  rule: r,
  problems,
  busy,
  onEdit,
  onDelete,
  onToggle,
}: {
  rule: QcpRoutingRule;
  problems: RoutingProblem[];
  busy: boolean;
  onEdit: () => void;
  onDelete: () => void;
  onToggle: () => void;
}) {
  const broken = problems.length > 0;
  return (
    <div className={cn("p-4", broken && "bg-amber-50/60")}>
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={onToggle}
          disabled={busy}
          title={
            r.is_blocked
              ? (r.blocked_detail ?? "This rule carries no traffic.")
              : r.is_active
                ? "Deactivate — the sender will ignore this rule"
                : "Activate — QCP re-runs every guard before allowing it"
          }
        >
          <Badge
            variant={
              r.is_effectively_live
                ? "success"
                : r.is_blocked && r.is_active
                  ? "warn"
                  : "default"
            }
            className="cursor-pointer text-[11px]"
          >
            {r.is_effectively_live
              ? "Active"
              : r.is_blocked && r.is_active
                ? "Blocked"
                : "Inactive"}
          </Badge>
        </button>
        <code className="text-sm font-medium">{r.intent}</code>
        <Badge variant="outline" className="text-[11px]">
          {r.locale ?? "any locale"}
        </Badge>
        <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" />
        <PurposeBadge purpose={r.purpose} />
        <code className="text-sm">{r.template_intent}</code>
        <span className="ml-auto text-xs text-muted-foreground">
          priority {r.priority}
        </span>
        <div className="flex items-center gap-1">
          <Button
            size="sm"
            variant="ghost"
            onClick={onEdit}
            aria-label={`Edit rule for ${r.intent}`}
          >
            <Pencil className="h-3.5 w-3.5" />
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="text-rose-700"
            onClick={onDelete}
            aria-label={`Delete rule for ${r.intent}`}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
      {r.fallback_channel && (
        <div className="mt-1.5 text-xs text-muted-foreground">
          Falls back to {r.fallback_channel} when WhatsApp is unavailable.
        </div>
      )}
      {broken && (
        <ul className="mt-2 grid gap-1 text-xs text-amber-900">
          {problems.map((p, i) => (
            <li key={i} className="break-words">
              {p.message}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/* ----------------------------------------------------------- create/edit */

function RuleDialog({
  rule,
  products,
  templates,
  onClose,
  onSaved,
}: {
  rule: QcpRoutingRule | null;
  products: QcpProduct[];
  templates: QcpTemplate[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const { write, busy } = useQcpWrite();
  const toast = useToast();
  const [productSlug, setProductSlug] = React.useState(
    rule?.product ?? products[0]?.slug ?? ""
  );
  const [purpose, setPurpose] = React.useState<"authentication" | "engagement">(
    rule?.purpose ?? "engagement"
  );
  const [templateIntent, setTemplateIntent] = React.useState(
    rule?.template_intent ?? ""
  );
  const [refusal, setRefusal] = React.useState<QcpRefusal | null>(null);

  const product = products.find((p) => p.slug === productSlug) ?? null;
  const granted = (product?.allowed_purposes ?? []).includes(purpose);

  // Only templates that actually sit on the chosen number can be routed to.
  const onThisNumber = templates.filter((t) => t.account_purpose === purpose);
  const chosen = onThisNumber.filter((t) => t.intent === templateIntent);
  const approved = chosen.filter((t) => t.status === "approved");

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setRefusal(null);
    const form = new FormData(e.currentTarget);
    const str = (k: string) => String(form.get(k) ?? "").trim();

    if (!productSlug) {
      setRefusal({
        title: "Pick a product",
        detail: "A rule belongs to exactly one product — that is what the sender matches on.",
        policy: true,
      });
      return;
    }
    if (!templateIntent) {
      setRefusal({
        title: "Pick a template",
        detail: `No template intent chosen. There ${
          onThisNumber.length === 1 ? "is 1 template" : `are ${onThisNumber.length} templates`
        } on the ${purpose} number to choose from.`,
        policy: true,
      });
      return;
    }
    const shared = {
      purpose,
      template_intent: templateIntent,
      locale: str("locale") || null,
      priority: Number(str("priority") || "100"),
      fallback_channel: str("fallback_channel") || null,
    };

    // Neither model accepts `is_active`. A new rule always lands inactive and
    // switching one on is its own route, so that the backend can re-run every
    // guard at the moment it matters rather than at the moment it was typed.
    const res = rule
      ? await write<{ problems?: QcpRuleProblem[] }>(QCP.routingRule(rule.id), {
          method: "PATCH",
          body: shared,
        })
      : await write<{ problems?: QcpRuleProblem[] }>(QCP.routingRules, {
          method: "POST",
          body: { product: productSlug, intent: str("intent"), ...shared },
        });

    if (!res.ok) {
      setRefusal(res.refusal);
      return;
    }
    const warnings = res.data?.problems ?? [];
    toast.success(
      rule ? "Rule updated" : "Rule created (inactive)",
      warnings.length
        ? warnings[0].detail
        : `${rule?.intent ?? str("intent")} → ${templateIntent} on ${
            purpose === "authentication" ? "Quata Verify" : "QUATA"
          }.${rule ? "" : " Switch it on from the list when you are ready."}`
    );
    onSaved();
    onClose();
  }

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{rule ? "Edit routing rule" : "New routing rule"}</DialogTitle>
          <DialogDescription>
            What one product&apos;s intent resolves to. A new rule is inactive by
            default — an inactive rule routes nothing, which is the safe way for it to
            exist while you check it.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={submit} className="grid gap-4 max-h-[70vh] overflow-y-auto pr-1">
          {refusal && (
            <RefusalBanner refusal={refusal} onDismiss={() => setRefusal(null)} />
          )}

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="product">Product *</Label>
              <Select
                id="product"
                value={productSlug}
                onChange={(e) => setProductSlug(e.target.value)}
              >
                <option value="">— Choose —</option>
                {products.map((p) => (
                  <option key={p.slug} value={p.slug}>
                    {p.name}
                    {p.is_enabled ? "" : " (disabled)"}
                  </option>
                ))}
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="intent">Intent the product asks for *</Label>
              <Input
                id="intent"
                name="intent"
                required
                defaultValue={rule?.intent ?? ""}
                placeholder="login_otp"
              />
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="purpose">Goes out on *</Label>
              <Select
                id="purpose"
                value={purpose}
                onChange={(e) => {
                  setPurpose(e.target.value as "authentication" | "engagement");
                  setTemplateIntent("");
                }}
              >
                <option value="authentication">Quata Verify — authentication</option>
                <option value="engagement">QUATA — engagement</option>
              </Select>
              {!granted && product && (
                <p className="text-[11px] text-rose-700">
                  {product.name} is not allowed to reach this number. Grant the purpose
                  on the Registry tab, or the send will be refused even with this rule
                  active.
                </p>
              )}
            </div>
            <div className="grid gap-2">
              <Label htmlFor="template_intent">Template *</Label>
              <Select
                id="template_intent"
                value={templateIntent}
                onChange={(e) => setTemplateIntent(e.target.value)}
              >
                <option value="">— Choose —</option>
                {[...new Set(onThisNumber.map((t) => t.intent))].map((intent) => {
                  const rows = onThisNumber.filter((t) => t.intent === intent);
                  const ok = rows.some((t) => t.status === "approved");
                  return (
                    <option key={intent} value={intent}>
                      {intent}
                      {ok ? "" : " — not approved"}
                    </option>
                  );
                })}
              </Select>
              <p className="text-[11px] text-muted-foreground">
                Only templates bound to the chosen number are listed — a template cannot
                be moved between numbers.
              </p>
            </div>
          </div>

          {onThisNumber.length === 0 && (
            <RefusalBanner
              refusal={{
                title: "No templates on that number",
                detail: `Nothing is registered on the ${purpose} number yet, so this rule has nothing to resolve to. Create the template first on the Templates tab.`,
                policy: true,
              }}
            />
          )}

          <div className="grid gap-3 sm:grid-cols-3">
            <div className="grid gap-2">
              <Label htmlFor="locale">Locale</Label>
              <Select id="locale" name="locale" defaultValue={rule?.locale ?? ""}>
                <option value="">any</option>
                <option value="en">en</option>
                <option value="fr">fr</option>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="priority">Priority</Label>
              <Input
                id="priority"
                name="priority"
                type="number"
                defaultValue={rule?.priority ?? 100}
              />
              <p className="text-[11px] text-muted-foreground">Lower wins.</p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="fallback_channel">Fallback channel</Label>
              <Select
                id="fallback_channel"
                name="fallback_channel"
                defaultValue={rule?.fallback_channel ?? ""}
              >
                <option value="">none</option>
                <option value="sms">sms</option>
                <option value="email">email</option>
              </Select>
            </div>
          </div>

          <Note tone={approved.length === 0 && templateIntent ? "warn" : "info"}>
            {rule
              ? "Saving does not change whether this rule is active. Switch it on or off from the Active badge in the list — QCP re-runs every guard at that moment."
              : "A new rule lands inactive and routes nothing. Switch it on from the list once you have checked it; QCP re-runs every guard then."}
            {approved.length === 0 && templateIntent
              ? ` Right now "${templateIntent}" has no approved template on this number, so activation would be refused.`
              : ""}
          </Note>

          <DialogFooter className="pt-2">
            <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
              Cancel
            </Button>
            <Button type="submit" disabled={busy}>
              {rule ? "Save rule" : "Create rule"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
