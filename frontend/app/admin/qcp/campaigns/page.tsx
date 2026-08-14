"use client";

/**
 * QCP campaigns — the marketing side, and the stop button.
 *
 * Two things this screen exists to make impossible to get wrong.
 *
 * **You cannot lose the stop button.** Every non-terminal campaign renders
 * "Stop" as a destructive action in its own row, at the same place, whatever
 * else is on screen. It is never behind a menu, never behind a detail view,
 * and it is not gated on the permission that starting needs — anyone who can
 * see a campaign can halt it. Somebody will send the wrong thing to the wrong
 * audience; the only question is whether they can stop it in one click.
 *
 * **You cannot mistake dormant for broken.** QCP ships switched off, so a
 * screen with no campaigns and nothing that can send is the *correct* state
 * on a fresh install. Loading, failed-to-load and correctly-empty are three
 * different renders here, and the empty one says which of the several
 * reasons applies — delivery off, no engagement number, no enabled product —
 * because "it looks broken so I fixed it" is how a working dormancy gate gets
 * switched on.
 *
 * Everything else follows the other QCP screens: `PageShell` + `QcpTabs`,
 * `useApi` for reads, `useQcpWrite` for writes, and a `RefusalBanner` where
 * the operator caused the refusal. A campaign refusal is the same
 * `409 {reason, detail}` shape the templates and routing screens already
 * render, so `explainQcpRefusal` handles it unchanged.
 */

import * as React from "react";
import {
  AlertTriangle,
  BellOff,
  CircleStop,
  Gauge,
  Megaphone,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Users,
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
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { useQcpWrite, type QcpRefusal } from "../api";
import {
  CATEGORY_STYLE,
  Loading,
  LoadError,
  Note,
  PurposeBadge,
  QcpTabs,
  RefusalBanner,
  StatusBadge,
  fmt,
  relative,
} from "../shared";
import {
  CAMPAIGNS,
  CAMPAIGN_STATUSES,
  CAMPAIGN_STATUS_TONE,
  RECIPIENT_STATUS_TONE,
  type AudiencePreview,
  type Campaign,
  type CampaignDetail,
  type CampaignListResponse,
  type CampaignPlatform,
  type OptOutListResponse,
} from "./api";

/** Starting a campaign reaches the whole fleet's number. Stopping does not. */
const PERM_OPERATE = "whatsapp:operate";

export default function QcpCampaignsPage() {
  return (
    <PageShell
      title="QCP campaigns"
      description="Marketing sends on the QUATA number. A campaign is an audience, an approved template, a pace and a stop button — it can never go out on Quata Verify, and it can never start while QCP is dormant."
      requirePermission="settings:manage"
    >
      <QcpTabs />
      <Campaigns />
    </PageShell>
  );
}

function Campaigns() {
  const [statusFilter, setStatusFilter] = React.useState("");
  const [creating, setCreating] = React.useState(false);
  const [stopping, setStopping] = React.useState<Campaign | null>(null);
  const [starting, setStarting] = React.useState<Campaign | null>(null);
  const [detail, setDetail] = React.useState<string | null>(null);
  const [refusal, setRefusal] = React.useState<QcpRefusal | null>(null);

  const { write, busy } = useQcpWrite();
  const toast = useToast();
  const { hasPermission } = useAuth();
  const canOperate = hasPermission(PERM_OPERATE);

  const qs = statusFilter ? `?status=${encodeURIComponent(statusFilter)}` : "";
  const { data, error, loading, refresh } = useApi<CampaignListResponse>(
    `${CAMPAIGNS.list}${qs}`
  );
  const optOuts = useApi<OptOutListResponse>(CAMPAIGNS.optOuts);

  async function act(
    path: string,
    body: unknown,
    onOk: (result: unknown) => void
  ) {
    setRefusal(null);
    const res = await write(path, { method: "POST", body });
    if (!res.ok) {
      setRefusal(res.refusal);
      return;
    }
    onOk(res.data);
    refresh();
  }

  if (loading && !data) return <Loading label="Loading campaigns…" />;
  if (error) return <LoadError error={error} onRetry={refresh} />;
  if (!data) return <Loading label="Loading campaigns…" />;

  const platform = data.platform;
  const blockers = startBlockers(platform);
  const canCreate = platform.products.length > 0 && !!platform.engagement_account;

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <Select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="w-auto"
          aria-label="Filter by campaign state"
        >
          <option value="">All states</option>
          {CAMPAIGN_STATUSES.map((s) => (
            <option key={s} value={s}>
              {s.replace(/_/g, " ")}
            </option>
          ))}
        </Select>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <Button variant="outline" size="sm" onClick={refresh}>
            <RefreshCw className="h-3.5 w-3.5" /> Refresh
          </Button>
          <Button size="sm" onClick={() => setCreating(true)} disabled={!canCreate}>
            <Plus className="h-3.5 w-3.5" /> New campaign
          </Button>
        </div>
      </div>

      {refusal && <RefusalBanner refusal={refusal} onDismiss={() => setRefusal(null)} />}

      <PlatformState platform={platform} blockers={blockers} />

      {data.items.length === 0 ? (
        <EmptyState
          icon={Megaphone}
          title="No campaigns yet"
          description={
            canCreate
              ? "Nothing has ever been drafted. A campaign starts as a draft, is aimed at an audience built from QCP's own contacts, and does not send until it is started deliberately."
              : "There is nothing to draft a campaign against yet — a campaign needs a live QUATA number and at least one enabled product in the registry."
          }
          action={
            canCreate ? (
              <Button size="sm" onClick={() => setCreating(true)}>
                <Plus className="h-3.5 w-3.5" /> New campaign
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="grid gap-3">
          {data.items.map((campaign) => (
            <CampaignCard
              key={campaign.campaign_uid}
              campaign={campaign}
              busy={busy}
              canOperate={canOperate}
              onOpen={() => setDetail(campaign.campaign_uid)}
              onBuildAudience={() =>
                act(CAMPAIGNS.audience(campaign.campaign_uid), undefined, (result) => {
                  const size = (result as { size?: number })?.size ?? 0;
                  toast.success(
                    "Audience built",
                    `${size} recipient${size === 1 ? "" : "s"} after opt-outs were removed.`
                  );
                })
              }
              onStart={() => setStarting(campaign)}
              onPause={() =>
                act(CAMPAIGNS.pause(campaign.campaign_uid), {}, () =>
                  toast.success("Campaign paused", "Nothing further will be sent until it is resumed.")
                )
              }
              onStop={() => setStopping(campaign)}
            />
          ))}
        </div>
      )}

      <OptOutPanel
        optOuts={optOuts.data ?? null}
        error={optOuts.error}
        loading={optOuts.loading}
        onChanged={() => {
          optOuts.refresh();
          refresh();
        }}
      />

      {creating && (
        <CreateDialog
          platform={platform}
          onClose={() => setCreating(false)}
          onCreated={() => {
            setCreating(false);
            refresh();
          }}
        />
      )}

      {detail && <DetailDialog uid={detail} onClose={() => setDetail(null)} />}

      <ConfirmDialog
        open={!!starting}
        onOpenChange={(v) => !v && setStarting(null)}
        title={`Start "${starting?.name ?? "campaign"}"?`}
        description={
          starting
            ? `This sends to ${starting.audience_size} recipient${
                starting.audience_size === 1 ? "" : "s"
              } on ${starting.account_name ?? "QUATA"}, at ${
                starting.messages_per_minute
              } messages a minute. It can be stopped at any point, and everyone who has opted out is skipped.`
            : undefined
        }
        confirmLabel="Start sending"
        onConfirm={async () => {
          if (!starting) return;
          const target = starting;
          setStarting(null);
          await act(CAMPAIGNS.start(target.campaign_uid), undefined, () =>
            toast.success(
              "Campaign started",
              `${target.name} is sending at ${target.messages_per_minute}/minute. Stop is available on its row.`
            )
          );
        }}
      />

      <ConfirmDialog
        open={!!stopping}
        onOpenChange={(v) => !v && setStopping(null)}
        title={`Stop "${stopping?.name ?? "campaign"}" now?`}
        description="Sending halts immediately — the current message finishes and nothing else goes out. Everyone not yet messaged is cancelled. This cannot be undone: a stopped campaign is never restarted, so that the record of what actually went out stays true."
        confirmLabel="Stop the campaign"
        destructive
        onConfirm={async () => {
          if (!stopping) return;
          const target = stopping;
          setStopping(null);
          await act(
            CAMPAIGNS.stop(target.campaign_uid),
            { reason: "stopped from the console" },
            (result) => {
              const cancelled = (result as { cancelled?: number })?.cancelled ?? 0;
              toast.success(
                "Campaign stopped",
                `${cancelled} recipient${cancelled === 1 ? "" : "s"} were cancelled before being messaged.`
              );
            }
          );
        }}
      />
    </div>
  );
}

/* --------------------------------------------------------- platform state */

/**
 * Every reason a campaign could not send right now, in the order an operator
 * would fix them. An empty list means the platform is ready — which on a
 * fresh install it deliberately is not.
 */
function startBlockers(platform: CampaignPlatform): string[] {
  const out: string[] = [];
  if (!platform.delivery_enabled) {
    out.push(
      "WhatsApp delivery is switched off. Both the environment kill switch and the admin toggle have to say yes before anything can leave QCP."
    );
  }
  if (!platform.engagement_account) {
    out.push(
      "There is no live QUATA number. Campaigns go out on the engagement number and nowhere else."
    );
  }
  if (!platform.any_product_enabled) {
    out.push(
      "No product is enabled in the registry, so no route exists for a campaign to travel on."
    );
  }
  return out;
}

function PlatformState({
  platform,
  blockers,
}: {
  platform: CampaignPlatform;
  blockers: string[];
}) {
  if (blockers.length === 0) {
    return (
      <Note>
        Delivery is on and {platform.engagement_account_name ?? "the QUATA number"} is
        live. A campaign still starts as a draft and only sends once it is started
        deliberately — capped at {platform.max_messages_per_minute} messages a minute
        and {platform.max_audience.toLocaleString()} recipients.
      </Note>
    );
  }
  return (
    <div className="rounded-2xl border border-border bg-surface-soft p-4">
      <div className="flex items-start gap-2">
        <Gauge className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
        <div className="min-w-0">
          <div className="text-sm font-semibold">
            QCP is dormant — no campaign can send
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            This is the expected state on an install that has never been switched on.
            Campaigns can still be drafted and aimed; starting one is refused until
            every line below is resolved.
          </p>
          <ul className="mt-2 grid gap-1.5 text-xs text-muted-foreground">
            {blockers.map((line) => (
              <li key={line} className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0 text-amber-600" />
                <span>{line}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ card */

function CampaignCard({
  campaign,
  busy,
  canOperate,
  onOpen,
  onBuildAudience,
  onStart,
  onPause,
  onStop,
}: {
  campaign: Campaign;
  busy: boolean;
  canOperate: boolean;
  onOpen: () => void;
  onBuildAudience: () => void;
  onStart: () => void;
  onPause: () => void;
  onStop: () => void;
}) {
  const terminal = campaign.status === "stopped" || campaign.status === "completed";
  const editable = campaign.status === "draft" || campaign.status === "scheduled";
  const r = campaign.results;

  return (
    <section className="rounded-2xl border border-border bg-card p-4 ring-soft">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={onOpen}
          className="text-sm font-semibold tracking-tight underline-offset-4 hover:underline"
        >
          {campaign.name}
        </button>
        <StatusBadge value={campaign.status} tones={CAMPAIGN_STATUS_TONE} />
        <PurposeBadge purpose={campaign.account_purpose} />
        {campaign.template_category && (
          <Badge variant="outline" className={CATEGORY_STYLE[campaign.template_category]}>
            {campaign.template_category}
          </Badge>
        )}
        <span className="text-xs text-muted-foreground">
          {campaign.product_name ?? campaign.product ?? "no product"} · {campaign.intent}
          {campaign.locale ? ` · ${campaign.locale}` : ""}
        </span>

        <div className="ml-auto flex flex-wrap items-center gap-1.5">
          {editable && (
            <Button variant="outline" size="sm" onClick={onBuildAudience} disabled={busy}>
              <Users className="h-3.5 w-3.5" />
              {campaign.audience_size > 0 ? "Rebuild audience" : "Build audience"}
            </Button>
          )}
          {!terminal && campaign.status !== "running" && (
            <Button
              size="sm"
              onClick={onStart}
              disabled={busy || !canOperate || campaign.audience_size === 0}
              title={
                canOperate
                  ? undefined
                  : "Starting a campaign needs the whatsapp:operate permission — it puts marketing on the number the whole fleet's login codes go out from."
              }
            >
              <Play className="h-3.5 w-3.5" />
              {campaign.status === "paused" ? "Resume" : "Start"}
            </Button>
          )}
          {campaign.status === "running" && (
            <Button variant="outline" size="sm" onClick={onPause} disabled={busy}>
              <Pause className="h-3.5 w-3.5" /> Pause
            </Button>
          )}
          {/* The stop button. Always in the same place, never behind a menu,
              and deliberately not gated on `whatsapp:operate` — halting is the
              safe direction and the person watching it go wrong may not be
              the person who started it. */}
          {!terminal && (
            <Button variant="destructive" size="sm" onClick={onStop} disabled={busy}>
              <CircleStop className="h-3.5 w-3.5" /> Stop
            </Button>
          )}
        </div>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span>
          template <code>{campaign.template ?? "—"}</code>
          {campaign.template_status ? ` (${campaign.template_status})` : ""}
        </span>
        <span>{campaign.audience_label ?? campaign.audience_source}</span>
        <span>{campaign.messages_per_minute}/min</span>
        {campaign.scheduled_at && <span>scheduled {fmt(campaign.scheduled_at)}</span>}
        {campaign.started_at && <span>started {relative(campaign.started_at)}</span>}
        {campaign.stopped_at && <span>stopped {relative(campaign.stopped_at)}</span>}
      </div>

      {campaign.stop_reason && (
        <p className="mt-2 text-xs text-rose-700">Stopped: {campaign.stop_reason}</p>
      )}
      {campaign.last_error && !campaign.stop_reason && (
        <p className="mt-2 text-xs text-amber-700">Last problem: {campaign.last_error}</p>
      )}

      <ResultsRow results={r} />
    </section>
  );
}

/**
 * The five numbers the brief asks for, plus the two that explain a gap.
 *
 * `sent`, `delivered` and `read` are cumulative — a read message is counted in
 * all three — so they are laid out as a progression rather than as separate
 * buckets, and the label says so.
 */
function ResultsRow({ results }: { results: Campaign["results"] }) {
  const cells: { label: string; value: number; tone?: string }[] = [
    { label: "audience", value: results.audience },
    { label: "queued", value: results.queued },
    { label: "sent", value: results.sent },
    { label: "delivered", value: results.delivered },
    { label: "read", value: results.read },
    { label: "failed", value: results.failed, tone: "text-rose-700" },
    { label: "suppressed", value: results.suppressed, tone: "text-amber-700" },
    { label: "opted out", value: results.opted_out, tone: "text-amber-700" },
    { label: "cancelled", value: results.cancelled },
  ];
  return (
    <>
      <div className="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-5 lg:grid-cols-9">
        {cells.map((cell) => (
          <div
            key={cell.label}
            className="rounded-xl border border-border bg-surface-soft px-2.5 py-2"
          >
            <div className={cn("text-lg font-semibold tracking-tight", cell.tone)}>
              {cell.value}
            </div>
            <div className="text-[11px] text-muted-foreground">{cell.label}</div>
          </div>
        ))}
      </div>
      <p className="mt-1.5 text-[11px] text-muted-foreground">
        Sent, delivered and read are cumulative, not separate groups — Meta&apos;s status
        ladder only moves forward, so a message that was read is counted in all three.
      </p>
    </>
  );
}

/* ---------------------------------------------------------------- create */

function CreateDialog({
  platform,
  onClose,
  onCreated,
}: {
  platform: CampaignPlatform;
  onClose: () => void;
  onCreated: () => void;
}) {
  const { write, busy } = useQcpWrite();
  const toast = useToast();
  const [product, setProduct] = React.useState(platform.products[0]?.slug ?? "");
  const [source, setSource] = React.useState(
    platform.audience_sources[0]?.value ?? "conversations"
  );
  const [filters, setFilters] = React.useState<{ state: string; days: string }>({
    state: "",
    days: "",
  });
  const [preview, setPreview] = React.useState<AudiencePreview | null>(null);
  const [refusal, setRefusal] = React.useState<QcpRefusal | null>(null);

  function filterPayload(): Record<string, unknown> {
    const out: Record<string, unknown> = {};
    if (source === "conversations") {
      if (filters.state) out.state = filters.state;
      if (filters.days) out.inbound_within_days = Number(filters.days);
    } else if (filters.days) {
      out.since_days = Number(filters.days);
    }
    return out;
  }

  async function onPreview() {
    setRefusal(null);
    const res = await write<AudiencePreview>(CAMPAIGNS.audiencePreview, {
      method: "POST",
      body: {
        product,
        audience_source: source,
        audience_filters: filterPayload(),
      },
    });
    if (!res.ok) {
      setPreview(null);
      setRefusal(res.refusal);
      return;
    }
    setPreview(res.data);
  }

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setRefusal(null);
    const form = new FormData(e.currentTarget);
    const str = (k: string) => String(form.get(k) ?? "").trim();
    const variables = str("variables")
      .split("|")
      .map((v) => v.trim())
      .filter(Boolean);

    const res = await write(CAMPAIGNS.create, {
      method: "POST",
      body: {
        name: str("name"),
        product,
        intent: str("intent"),
        locale: str("locale") || null,
        audience_source: source,
        audience_filters: filterPayload(),
        variables,
        messages_per_minute: Number(str("rate") || 20),
      },
    });
    if (!res.ok) {
      setRefusal(res.refusal);
      return;
    }
    toast.success(
      "Campaign drafted",
      `${str("name")} is a draft. Build its audience, then start it deliberately — nothing has been sent.`
    );
    onCreated();
  }

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>New campaign</DialogTitle>
          <DialogDescription>
            A campaign is routed like every other QCP message: it names a product and an
            intent, and the routing table decides which approved template carries it.
            That is why it can only ever go out on QUATA. Creating it sends nothing.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={submit} className="grid gap-4 max-h-[70vh] overflow-y-auto pr-1">
          {refusal && (
            <RefusalBanner refusal={refusal} onDismiss={() => setRefusal(null)} />
          )}

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="name">Campaign name *</Label>
              <Input id="name" name="name" required placeholder="Weekend promo" />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="product">Product *</Label>
              <Select
                id="product"
                value={product}
                onChange={(e) => setProduct(e.target.value)}
              >
                {platform.products.map((p) => (
                  <option key={p.slug} value={p.slug}>
                    {p.name}
                  </option>
                ))}
              </Select>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <div className="grid gap-2">
              <Label htmlFor="intent">Intent *</Label>
              <Input id="intent" name="intent" required placeholder="promo_weekend" />
              <p className="text-[11px] text-muted-foreground">
                Must already have an active engagement routing rule pointing at an
                approved template.
              </p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="locale">Language</Label>
              <Input id="locale" name="locale" placeholder="en" />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="rate">Messages per minute</Label>
              <Input
                id="rate"
                name="rate"
                type="number"
                min={1}
                max={platform.max_messages_per_minute}
                defaultValue={20}
              />
              <p className="text-[11px] text-muted-foreground">
                Max {platform.max_messages_per_minute}. Sending faster than Meta expects
                is what gets a number throttled.
              </p>
            </div>
          </div>

          <div className="grid gap-2">
            <Label htmlFor="variables">Template variables</Label>
            <Input
              id="variables"
              name="variables"
              placeholder="50% off | this weekend"
            />
            <p className="text-[11px] text-muted-foreground">
              One value per template placeholder, separated by <code>|</code>. The same
              values go to everybody — QCP has no customer database to personalise from,
              and will not invent one. The count must match the template exactly or the
              send is refused.
            </p>
          </div>

          <fieldset className="grid gap-3 rounded-xl border border-border bg-surface-soft p-3.5">
            <legend className="px-1 text-xs font-semibold">
              Audience — built from QCP&apos;s own contacts
            </legend>

            <div className="grid gap-3 sm:grid-cols-3">
              <div className="grid gap-2">
                <Label htmlFor="source">Source</Label>
                <Select
                  id="source"
                  value={source}
                  onChange={(e) => {
                    setSource(e.target.value);
                    setPreview(null);
                  }}
                >
                  {platform.audience_sources.map((s) => (
                    <option key={s.value} value={s.value}>
                      {s.label}
                    </option>
                  ))}
                </Select>
              </div>
              {source === "conversations" && (
                <div className="grid gap-2">
                  <Label htmlFor="conv-state">Thread state</Label>
                  <Select
                    id="conv-state"
                    value={filters.state}
                    onChange={(e) => {
                      setFilters((f) => ({ ...f, state: e.target.value }));
                      setPreview(null);
                    }}
                  >
                    <option value="">Any</option>
                    <option value="open">Open</option>
                    <option value="snoozed">Snoozed</option>
                    <option value="closed">Closed</option>
                  </Select>
                </div>
              )}
              <div className="grid gap-2">
                <Label htmlFor="days">
                  {source === "conversations" ? "Messaged us within" : "Reached within"}
                </Label>
                <Input
                  id="days"
                  type="number"
                  min={1}
                  max={3650}
                  value={filters.days}
                  placeholder="days (any)"
                  onChange={(e) => {
                    setFilters((f) => ({ ...f, days: e.target.value }));
                    setPreview(null);
                  }}
                />
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Button type="button" variant="outline" size="sm" onClick={onPreview} disabled={busy}>
                <Users className="h-3.5 w-3.5" /> Preview audience
              </Button>
              {preview && (
                <span className="text-xs text-muted-foreground">
                  <strong className="text-foreground">{preview.eligible}</strong> eligible
                  · {preview.matched} matched · {preview.opted_out} removed for consent
                  {preview.capped && ` · capped at ${preview.limit}`}
                </span>
              )}
            </div>
            {preview && preview.sample.length > 0 && (
              <p className="text-[11px] text-muted-foreground break-words">
                For example: {preview.sample.slice(0, 5).join(", ")}
              </p>
            )}
            {preview && preview.eligible === 0 && (
              <Note tone="warn">
                Nobody matches. QCP builds audiences only from conversations and
                messages it already holds on the QUATA number — there is no contact
                list to import, by design.
              </Note>
            )}
          </fieldset>

          <DialogFooter className="pt-2">
            <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
              Cancel
            </Button>
            <Button type="submit" disabled={busy || !product}>
              Create draft
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/* ---------------------------------------------------------------- detail */

function DetailDialog({ uid, onClose }: { uid: string; onClose: () => void }) {
  const { data, error, loading, refresh } = useApi<CampaignDetail>(CAMPAIGNS.one(uid));

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>{data?.name ?? "Campaign"}</DialogTitle>
          <DialogDescription>
            Every address in this campaign and what happened when QCP handed it off.
            Delivery beyond that is the message log&apos;s own record — this screen never
            keeps a second copy of it.
          </DialogDescription>
        </DialogHeader>

        <div className="max-h-[70vh] overflow-y-auto pr-1">
          {loading && !data && <Loading label="Loading recipients…" />}
          {error && <LoadError error={error} onRetry={refresh} />}
          {data && data.recipients.length === 0 && (
            <EmptyState
              icon={Users}
              title="No audience built yet"
              description="This campaign has been drafted but never aimed. Build its audience to see who it would reach."
            />
          )}
          {data && data.recipients.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="text-muted-foreground">
                  <tr className="border-b border-border">
                    <th className="py-2 pr-3 font-medium">Number</th>
                    <th className="py-2 pr-3 font-medium">Hand-off</th>
                    <th className="py-2 pr-3 font-medium">Attempted</th>
                    <th className="py-2 font-medium">Note</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recipients.map((row) => (
                    <tr key={row.phone_e164} className="border-b border-border/60">
                      <td className="py-2 pr-3 font-mono">{row.phone_e164}</td>
                      <td className="py-2 pr-3">
                        <StatusBadge value={row.status} tones={RECIPIENT_STATUS_TONE} />
                      </td>
                      <td className="py-2 pr-3 text-muted-foreground">
                        {fmt(row.attempted_at)}
                      </td>
                      <td className="py-2 text-muted-foreground break-words">
                        {row.last_error ?? "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* -------------------------------------------------------------- opt-outs */

/**
 * The consent list.
 *
 * Rendered on the same screen as the campaigns rather than behind a tab,
 * because it is the number that decides whether this platform is safe to
 * operate: Meta restricts a number that generates block reports, and QCP has
 * two numbers, one of which carries the fleet's login codes.
 *
 * There is no remove button, and there is no route behind one. A customer's
 * "stop" is not undone from a console.
 */
function OptOutPanel({
  optOuts,
  error,
  loading,
  onChanged,
}: {
  optOuts: OptOutListResponse | null;
  error: Error | null;
  loading: boolean;
  onChanged: () => void;
}) {
  const { write, busy } = useQcpWrite();
  const toast = useToast();
  const [phone, setPhone] = React.useState("");
  const [refusal, setRefusal] = React.useState<QcpRefusal | null>(null);

  async function add() {
    if (!phone.trim()) return;
    setRefusal(null);
    const res = await write(CAMPAIGNS.optOuts, {
      method: "POST",
      body: { phone_e164: phone.trim(), note: "recorded in the console" },
    });
    if (!res.ok) {
      setRefusal(res.refusal);
      return;
    }
    setPhone("");
    toast.success("Opt-out recorded", "This number will be skipped by every campaign.");
    onChanged();
  }

  async function scan() {
    setRefusal(null);
    const res = await write<{ scanned: number; opted_out: number }>(CAMPAIGNS.optOutScan, {
      method: "POST",
    });
    if (!res.ok) {
      setRefusal(res.refusal);
      return;
    }
    toast.success(
      "Replies scanned",
      `${res.data.opted_out} new opt-out${res.data.opted_out === 1 ? "" : "s"} from ${res.data.scanned} inbound message(s).`
    );
    onChanged();
  }

  return (
    <section className="rounded-2xl border border-border bg-card p-4 ring-soft">
      <div className="flex flex-wrap items-center gap-2">
        <BellOff className="h-4 w-4 text-muted-foreground" />
        <h3 className="text-sm font-semibold tracking-tight">Opted out</h3>
        <Badge variant="outline">{optOuts?.total ?? 0}</Badge>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <Input
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="+237…"
            className="w-44"
            aria-label="Number to opt out"
          />
          <Button variant="outline" size="sm" onClick={add} disabled={busy || !phone.trim()}>
            Add
          </Button>
          <Button variant="outline" size="sm" onClick={scan} disabled={busy}>
            <RefreshCw className="h-3.5 w-3.5" /> Scan replies
          </Button>
        </div>
      </div>

      <p className="mt-1.5 text-xs text-muted-foreground">
        A customer opts out in one step: they reply <strong>STOP</strong> — or{" "}
        <strong>ARRÊT</strong>, <strong>DÉSABONNER</strong>, <strong>UNSUBSCRIBE</strong>{" "}
        — to the message they received, in English or French. Campaigns honour it before
        the next message goes out. Nothing on this screen removes an opt-out.
      </p>

      {refusal && (
        <div className="mt-3">
          <RefusalBanner refusal={refusal} onDismiss={() => setRefusal(null)} />
        </div>
      )}

      <div className="mt-3">
        {loading && !optOuts && <Loading label="Loading opt-outs…" />}
        {error && <LoadError error={error} />}
        {optOuts && optOuts.items.length === 0 && (
          <EmptyState
            icon={BellOff}
            title="Nobody has opted out"
            description="On an install that has never sent a campaign this is the expected state, not a missing feature."
          />
        )}
        {optOuts && optOuts.items.length > 0 && (
          <ul className="grid gap-1.5 text-xs">
            {optOuts.items.map((row) => (
              <li key={row.phone_e164} className="flex flex-wrap items-center gap-2">
                <span className="font-mono">{row.phone_e164}</span>
                <Badge variant="outline" className="text-[11px]">
                  {row.source === "inbound_keyword" ? "replied" : "recorded by an admin"}
                </Badge>
                <span className="text-muted-foreground">
                  {row.evidence ?? row.note ?? ""} · {relative(row.created_at)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
