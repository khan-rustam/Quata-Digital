"use client";

/**
 * QCP registry — which QUATA products may call QCP, and what state their key
 * is in.
 *
 * `is_enabled` is the per-product migration gate and it defaults to false.
 * That is what lets QCP run alongside the existing fleet without taking any
 * traffic: QuataFood and QuataPay keep sending exactly as they do today
 * until someone deliberately migrates one.
 *
 * The four write paths here are deliberately four, not one form:
 *
 *   * **Register** creates a product engagement-only, disabled and keyless.
 *     None of those three can be set at registration, so registering can
 *     never be the act that opens an authentication path or starts traffic.
 *   * **Reachable numbers** may *remove* the authentication purpose freely.
 *   * **Granting authentication** is its own control with its own mandatory
 *     justification, because it is the one that puts a product's traffic
 *     beside the fleet's OTP path — and that must not happen as one checkbox
 *     among many in a form somebody opened to change a rate limit.
 *   * **Key** and **enablement** are separate again, so "registered", "can
 *     authenticate" and "may send" are three distinct, separately audited
 *     states.
 *
 * **No stored API key is shown here, and none could be.** QCP stores the
 * sha256 of a product key and a non-reversible display prefix — never the
 * key. The plaintext exists for exactly one render, in `MintedKeyDialog`,
 * immediately after minting; it is held in component state, never written
 * anywhere, and discarded when the dialog closes.
 */

import * as React from "react";
import {
  Ban,
  Blocks,
  KeyRound,
  Pencil,
  Plus,
  Power,
  RefreshCw,
  TriangleAlert,
  Waypoints,
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
import { QCP, useQcpWrite, type QcpMintedKey, type QcpRefusal } from "../api";
import {
  CopyButton,
  Loading,
  LoadError,
  Note,
  PurposeBadge,
  QcpTabs,
  RefusalBanner,
  TypeToConfirm,
  fmt,
  relative,
  type QcpProductRegistryItem,
} from "../shared";

type RegistryResponse = {
  items: QcpProductRegistryItem[];
  platform_templates: number;
};

export default function QcpProductsPage() {
  return (
    <PageShell
      title="QCP registry"
      description="The plugin registry: which QUATA products may call QCP. A product takes no traffic until it is explicitly enabled here — that flag is the per-product migration gate."
      requirePermission="settings:manage"
    >
      <QcpTabs />
      <Registry />
    </PageShell>
  );
}

function Registry() {
  const { data, error, loading, refresh } = useApi<RegistryResponse>(QCP.products);
  const { write, mintProductKey, busy } = useQcpWrite();
  const toast = useToast();

  const [registering, setRegistering] = React.useState(false);
  const [editing, setEditing] = React.useState<QcpProductRegistryItem | null>(null);
  const [purposesFor, setPurposesFor] = React.useState<QcpProductRegistryItem | null>(null);
  const [toggling, setToggling] = React.useState<QcpProductRegistryItem | null>(null);
  const [rotating, setRotating] = React.useState<QcpProductRegistryItem | null>(null);
  const [revoking, setRevoking] = React.useState<QcpProductRegistryItem | null>(null);
  const [minted, setMinted] = React.useState<QcpMintedKey | null>(null);
  const [refusal, setRefusal] = React.useState<QcpRefusal | null>(null);

  async function onMint(p: QcpProductRegistryItem) {
    setRefusal(null);
    const res = await mintProductKey(p.slug);
    setRotating(null);
    if (!res.ok) {
      setRefusal(res.refusal);
      return;
    }
    setMinted(res.data);
    refresh();
  }

  async function onRevoke() {
    if (!revoking) return;
    const res = await write(QCP.productApiKey(revoking.slug), { method: "DELETE" });
    setRevoking(null);
    if (!res.ok) {
      setRefusal(res.refusal);
      return;
    }
    toast.success(
      "Key revoked",
      `${revoking.name} can no longer authenticate to QCP. Its calls will 401 from now on.`
    );
    refresh();
  }

  async function onToggle() {
    if (!toggling) return;
    const next = !toggling.is_enabled;
    const res = await write(
      next ? QCP.productEnable(toggling.slug) : QCP.productDisable(toggling.slug),
      { method: "POST" }
    );
    setToggling(null);
    if (!res.ok) {
      setRefusal(res.refusal);
      return;
    }
    toast.success(
      next ? `${toggling.name} enabled` : `${toggling.name} disabled`,
      next
        ? "It may now call QCP. Whether anything is delivered still depends on the number being active and delivery being on."
        : "Its calls are refused before Meta is contacted, and show up as suppressions. Its key survives, so re-enabling is one click."
    );
    refresh();
  }

  if (loading && !data) return <Loading label="Loading registry…" />;
  if (error) return <LoadError error={error} onRetry={refresh} />;
  if (!data) return <Loading label="Loading registry…" />;

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-start gap-2">
        <Note>
          Keys are stored as a sha256 hash and a non-reversible display prefix. The
          value itself does not exist anywhere in this system, so it cannot be shown,
          copied or recovered — only rotated. You see it once, at mint, and never again.
        </Note>
        <div className="ml-auto flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={refresh}>
            <RefreshCw className="h-3.5 w-3.5" /> Refresh
          </Button>
          <Button size="sm" onClick={() => setRegistering(true)}>
            <Plus className="h-3.5 w-3.5" /> Register product
          </Button>
        </div>
      </div>

      {refusal && <RefusalBanner refusal={refusal} onDismiss={() => setRefusal(null)} />}

      {data.items.length === 0 ? (
        <EmptyState
          icon={Blocks}
          title="No products registered"
          description="Nothing may call QCP — which is the correct state for a platform no product has migrated to yet. Register one to begin; it arrives disabled, keyless and engagement-only."
          action={
            <Button onClick={() => setRegistering(true)}>
              <Plus className="h-4 w-4" /> Register product
            </Button>
          }
        />
      ) : (
        <>
          <div className="grid gap-3 lg:grid-cols-2">
            {data.items.map((p) => (
              <ProductCard
                key={p.id}
                product={p}
                busy={busy}
                onEdit={() => setEditing(p)}
                onPurposes={() => setPurposesFor(p)}
                onToggle={() => setToggling(p)}
                onMint={() => (p.has_api_key ? setRotating(p) : onMint(p))}
                onRevoke={() => setRevoking(p)}
              />
            ))}
          </div>
          {data.items.every((p) => !p.is_enabled) && (
            <Note>
              Every product is disabled. That is the shipped state and it is why QCP
              takes no traffic — each product is migrated deliberately, one at a time.
            </Note>
          )}
          {data.platform_templates > 0 && (
            <p className="text-xs text-muted-foreground">
              {data.platform_templates} platform-owned template
              {data.platform_templates === 1 ? "" : "s"} belong to no product.
            </p>
          )}
        </>
      )}

      {registering && (
        <RegisterDialog
          onClose={() => setRegistering(false)}
          onSaved={refresh}
        />
      )}

      {editing && (
        <EditProductDialog
          key={editing.slug}
          product={editing}
          onClose={() => setEditing(null)}
          onSaved={refresh}
        />
      )}

      {purposesFor && (
        <PurposesDialog
          key={purposesFor.slug}
          product={purposesFor}
          onClose={() => setPurposesFor(null)}
          onSaved={refresh}
        />
      )}

      {toggling && (
        <EnablementDialog
          key={toggling.slug}
          product={toggling}
          onClose={() => setToggling(null)}
          onConfirm={onToggle}
          busy={busy}
        />
      )}

      <ConfirmDialog
        open={!!rotating}
        onOpenChange={(v) => !v && setRotating(null)}
        title={`Rotate the key for ${rotating?.name ?? "product"}?`}
        description="The current key stops working the moment the new one is minted — there is no overlap window. Anything still presenting the old key gets a 401. Have somewhere to put the new value before you do this."
        confirmLabel="Rotate key"
        destructive
        onConfirm={async () => {
          if (rotating) await onMint(rotating);
        }}
      />

      <ConfirmDialog
        open={!!revoking}
        onOpenChange={(v) => !v && setRevoking(null)}
        title={`Revoke the key for ${revoking?.name ?? "product"}?`}
        description="The stored hash is cleared. The product cannot authenticate at all until a new key is minted — no sha256 digest equals an empty string. Use this when a key has leaked."
        confirmLabel="Revoke key"
        destructive
        onConfirm={onRevoke}
      />

      {minted && (
        <MintedKeyDialog
          key={minted.fingerprint}
          minted={minted}
          onClose={() => setMinted(null)}
        />
      )}
    </div>
  );
}

function ProductCard({
  product: p,
  busy,
  onEdit,
  onPurposes,
  onToggle,
  onMint,
  onRevoke,
}: {
  product: QcpProductRegistryItem;
  busy: boolean;
  onEdit: () => void;
  onPurposes: () => void;
  onToggle: () => void;
  onMint: () => void;
  onRevoke: () => void;
}) {
  return (
    <div className="rounded-2xl border border-border bg-card p-5 ring-soft">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-base font-semibold tracking-tight">{p.name}</div>
          <div className="mt-0.5 text-xs text-muted-foreground">
            <code>{p.slug}</code>
            {p.registry_version && ` · spec ${p.registry_version}`}
          </div>
        </div>
        <Badge variant={p.is_enabled ? "success" : "default"}>
          {p.is_enabled ? "Enabled" : "Disabled"}
        </Badge>
      </div>

      {p.description && (
        <p className="mt-2 text-xs text-muted-foreground">{p.description}</p>
      )}

      <div className="mt-4 rounded-xl border border-border bg-surface-soft p-3">
        <div className="flex items-center gap-2 text-xs">
          <KeyRound className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="font-medium">API key</span>
          <Badge
            variant={p.has_api_key ? "success" : "warn"}
            className="ml-auto text-[11px]"
          >
            {p.has_api_key ? "Issued" : "Never issued"}
          </Badge>
        </div>
        <div className="mt-2 grid gap-1 text-xs text-muted-foreground">
          <div>
            Prefix:{" "}
            {p.api_key_prefix ? (
              <code className="text-foreground">{p.api_key_prefix}…</code>
            ) : (
              "—"
            )}
          </div>
          <div>Last authenticated call: {p.last_seen_at ? fmt(p.last_seen_at) : "never"}</div>
          {p.last_seen_at && <div>({relative(p.last_seen_at)})</div>}
        </div>
        {!p.has_api_key && (
          <p className="mt-2 text-[11px] text-muted-foreground">
            With no key stored, this product cannot authenticate at all — no sha256
            digest equals an empty string. Enabling it will be refused for that reason.
          </p>
        )}
        <div className="mt-3 flex flex-wrap gap-2">
          <Button size="sm" variant="outline" onClick={onMint} disabled={busy}>
            <KeyRound className="h-3.5 w-3.5" />
            {p.has_api_key ? "Rotate key" : "Mint key"}
          </Button>
          {p.has_api_key && (
            <Button
              size="sm"
              variant="ghost"
              className="text-rose-700"
              onClick={onRevoke}
              disabled={busy}
            >
              <Ban className="h-3.5 w-3.5" /> Revoke
            </Button>
          )}
        </div>
      </div>

      <div className="mt-3 grid gap-2 text-xs">
        <Row label="May reach">
          <div className="flex flex-wrap gap-1">
            {(p.allowed_purposes ?? []).length === 0 ? (
              <span className="text-muted-foreground">nothing</span>
            ) : (
              p.allowed_purposes.map((purpose) => (
                <PurposeBadge key={purpose} purpose={purpose} />
              ))
            )}
          </div>
        </Row>
        <Row label="Routing rules">
          <span>
            {p.routing_rules_active} active of {p.routing_rules}
          </span>
        </Row>
        <Row label="Templates">
          <span>{p.templates}</span>
        </Row>
        <Row label="Messages sent">
          <span>{p.messages}</span>
        </Row>
        <Row label="Rate limit">
          <span>{p.rate_limit_per_minute}/min · locale {p.default_locale}</span>
        </Row>
      </div>

      {p.is_enabled && p.routing_rules_active === 0 && (
        <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-2.5 text-[11px] text-amber-900">
          Enabled with no active routing rule. Every send this product attempts will be
          refused with &ldquo;no rule for that intent&rdquo; before Meta is contacted.
          Add one on the Routing tab.
        </p>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border pt-3">
        <Button size="sm" variant="outline" onClick={onEdit}>
          <Pencil className="h-3.5 w-3.5" /> Edit details
        </Button>
        <Button size="sm" variant="outline" onClick={onPurposes}>
          <Waypoints className="h-3.5 w-3.5" /> Reachable numbers
        </Button>
        <Button
          size="sm"
          variant={p.is_enabled ? "outline" : "default"}
          onClick={onToggle}
          disabled={busy}
        >
          <Power className="h-3.5 w-3.5" />
          {p.is_enabled ? "Disable" : "Enable"}
        </Button>
      </div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <span className="text-muted-foreground shrink-0">{label}</span>
      <div className="text-right min-w-0">{children}</div>
    </div>
  );
}

/* -------------------------------------------------------------------- edit */

/**
 * `ProductUpdateIn` accepts three fields and forbids everything else.
 *
 * Deliberately the *cosmetic* three. `slug` is the identity a live product
 * authenticates with; `allowed_purposes`, `is_enabled` and the key are the
 * gates, and each has its own control, its own audit action and — for two of
 * them — its own permission. Correcting a misspelt name must not be able to
 * open an authentication path or start traffic, so this form cannot offer it.
 *
 * Note the rate limit is what the console *displays*, not what the gateway
 * currently enforces (see `qcp_update_product`), so the field says so rather
 * than implying a cap that is not applied.
 */
function EditProductDialog({
  product: p,
  onClose,
  onSaved,
}: {
  product: QcpProductRegistryItem;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { write, busy } = useQcpWrite();
  const toast = useToast();
  const [refusal, setRefusal] = React.useState<QcpRefusal | null>(null);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setRefusal(null);
    const form = new FormData(e.currentTarget);
    const str = (k: string) => String(form.get(k) ?? "").trim();

    const name = str("name");
    const description = str("description");
    const rate = Number(str("rate_limit_per_minute"));

    // Send only what changed. The model refuses an empty body, and sending
    // an unchanged field would write an audit row saying nothing happened.
    const body: Record<string, unknown> = {};
    if (name !== p.name) body.name = name;
    if (description !== (p.description ?? "")) body.description = description || null;
    if (Number.isFinite(rate) && rate !== p.rate_limit_per_minute) {
      body.rate_limit_per_minute = rate;
    }
    if (Object.keys(body).length === 0) {
      setRefusal({
        title: "Nothing to save",
        detail: "No field was changed, so nothing was sent to QCP.",
        policy: true,
      });
      return;
    }

    const res = await write(QCP.product(p.slug), { method: "PATCH", body });
    if (!res.ok) {
      setRefusal(res.refusal);
      return;
    }
    toast.success("Product updated", `${p.slug} — ${Object.keys(body).join(", ")}.`);
    onSaved();
    onClose();
  }

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit {p.slug}</DialogTitle>
          <DialogDescription>
            Display details only. The slug, the reachable numbers, the gateway key
            and the enabled flag are not editable here — each has its own control.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={submit} className="grid gap-4">
          {refusal && (
            <RefusalBanner refusal={refusal} onDismiss={() => setRefusal(null)} />
          )}

          <div className="grid gap-2">
            <Label htmlFor="edit-name">Display name *</Label>
            <Input id="edit-name" name="name" required defaultValue={p.name} />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="edit-description">Description</Label>
            <Textarea
              id="edit-description"
              name="description"
              rows={3}
              defaultValue={p.description ?? ""}
            />
            <p className="text-[11px] text-muted-foreground">
              Clear the box to remove it.
            </p>
          </div>

          <div className="grid gap-2">
            <Label htmlFor="edit-rate">Rate limit (per minute) *</Label>
            <Input
              id="edit-rate"
              name="rate_limit_per_minute"
              type="number"
              min={1}
              max={100000}
              required
              defaultValue={p.rate_limit_per_minute}
            />
            <p className="text-[11px] text-muted-foreground">
              Recorded and audited under its own action. Note the gateway currently
              limits every product against one platform-wide cap, so this is what the
              console shows rather than what is enforced today.
            </p>
          </div>

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={busy}>
              Save changes
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/* ---------------------------------------------------------------- register */

/**
 * `ProductRegisterIn` accepts five fields and forbids everything else.
 *
 * Note what this form therefore cannot offer: allowed purposes, an enabled
 * flag, or key material. A newly registered product lands exactly where the
 * seeder leaves the four known ones — engagement-only, disabled, keyless —
 * and the form says so rather than pretending the omission is an oversight.
 */
function RegisterDialog({
  onClose,
  onSaved,
}: {
  onClose: () => void;
  onSaved: () => void;
}) {
  const { write, busy } = useQcpWrite();
  const toast = useToast();
  const [refusal, setRefusal] = React.useState<QcpRefusal | null>(null);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setRefusal(null);
    const form = new FormData(e.currentTarget);
    const str = (k: string) => String(form.get(k) ?? "").trim();

    const res = await write(QCP.products, {
      method: "POST",
      body: {
        slug: str("slug"),
        name: str("name"),
        description: str("description") || null,
        default_locale: str("default_locale") || "en",
        rate_limit_per_minute: Number(str("rate_limit_per_minute") || "600"),
      },
    });
    if (!res.ok) {
      setRefusal(res.refusal);
      return;
    }
    toast.success(
      "Product registered",
      `${str("name")} is registered, disabled, keyless and engagement-only. All three are separate, deliberate next steps.`
    );
    onSaved();
    onClose();
  }

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Register a product</DialogTitle>
          <DialogDescription>
            A newly registered product arrives disabled, with no API key, and able to
            reach the engagement number only. None of those can be set here.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={submit} className="grid gap-4 max-h-[70vh] overflow-y-auto pr-1">
          {refusal && (
            <RefusalBanner refusal={refusal} onDismiss={() => setRefusal(null)} />
          )}

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="slug">Slug *</Label>
              <Input id="slug" name="slug" required placeholder="quatapay" />
              <p className="text-[11px] text-muted-foreground">
                The product&apos;s identity in the <code>X-QCP-Product</code> header. It
                cannot be changed later.
              </p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="name">Name *</Label>
              <Input id="name" name="name" required placeholder="QuataPay" />
            </div>
          </div>

          <div className="grid gap-2">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              name="description"
              rows={2}
              placeholder="What this product sends over WhatsApp."
            />
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="default_locale">Default locale</Label>
              <Select id="default_locale" name="default_locale" defaultValue="en">
                <option value="en">en</option>
                <option value="fr">fr</option>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="rate_limit_per_minute">Rate limit (per minute)</Label>
              <Input
                id="rate_limit_per_minute"
                name="rate_limit_per_minute"
                type="number"
                min={1}
                defaultValue={600}
              />
            </div>
          </div>

          <Note>
            After registering: grant it the numbers it needs, mint its key, then enable
            it. Three separate, separately audited acts — so &ldquo;registered&rdquo;,
            &ldquo;can authenticate&rdquo; and &ldquo;may send&rdquo; never collapse
            into one click.
          </Note>

          <DialogFooter className="pt-2">
            <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
              Cancel
            </Button>
            <Button type="submit" disabled={busy}>
              Register (disabled, no key)
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/* ---------------------------------------------------------------- purposes */

/**
 * Which numbers a product may reach.
 *
 * The asymmetry is the point and it is the backend's, not a UI choice:
 * removing the authentication purpose is an ordinary edit, adding it is a
 * separate route with a mandatory justification. Reaching Quata Verify means
 * a product's traffic sits beside the fleet's OTP path, so granting it is the
 * kind of decision that should be answerable months later — and "because
 * <blank>" is worth nothing.
 */
function sameSet(a: string[], b: string[]) {
  return a.length === b.length && a.every((v) => b.includes(v));
}

function PurposesDialog({
  product,
  onClose,
  onSaved,
}: {
  product: QcpProductRegistryItem;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { write, busy } = useQcpWrite();
  const toast = useToast();
  const had = (product.allowed_purposes ?? []).includes("authentication");
  const [wantsAuth, setWantsAuth] = React.useState(had);
  const [wantsEngagement, setWantsEngagement] = React.useState(
    (product.allowed_purposes ?? []).includes("engagement")
  );
  const [justification, setJustification] = React.useState("");
  const [refusal, setRefusal] = React.useState<QcpRefusal | null>(null);

  const granting = !had && wantsAuth;
  const justified = justification.trim().length >= 8;
  const selected = [
    ...(wantsAuth ? ["authentication"] : []),
    ...(wantsEngagement ? ["engagement"] : []),
  ];
  const unchanged = sameSet(selected, product.allowed_purposes ?? []);

  async function submit() {
    setRefusal(null);

    // `PUT purposes` may remove authentication but never add it, so a grant
    // has to go through its own route first. Afterwards the ceiling is set
    // to exactly what was asked for — and by then that PUT is never *adding*
    // authentication, so it is always a legal call.
    if (granting) {
      const grant = await write<{ allowed_purposes?: string[] }>(
        QCP.productGrantAuthentication(product.slug),
        { method: "POST", body: { justification: justification.trim() } }
      );
      if (!grant.ok) {
        setRefusal(grant.refusal);
        return;
      }
      const after = grant.data?.allowed_purposes ?? [];
      if (!sameSet(after, selected)) {
        const res = await write(QCP.productPurposes(product.slug), {
          method: "PUT",
          body: { purposes: selected },
        });
        if (!res.ok) {
          setRefusal(res.refusal);
          return;
        }
      }
    } else {
      const res = await write(QCP.productPurposes(product.slug), {
        method: "PUT",
        body: { purposes: selected },
      });
      if (!res.ok) {
        setRefusal(res.refusal);
        return;
      }
    }

    toast.success(
      `${product.name} updated`,
      granting
        ? "It may now reach Quata Verify. The grant and your justification are on the audit row."
        : `May reach: ${selected.join(", ") || "nothing"}.`
    );
    onSaved();
    onClose();
  }

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Which numbers may {product.name} reach?</DialogTitle>
          <DialogDescription>
            The ceiling of what this product can ever ask for. It does not enable the
            product and it does not send anything.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-3">
          {refusal && (
            <RefusalBanner refusal={refusal} onDismiss={() => setRefusal(null)} />
          )}

          <label className="flex cursor-pointer items-start gap-2 rounded-xl border border-border bg-surface-soft p-3.5 text-xs">
            <input
              type="checkbox"
              checked={wantsEngagement}
              onChange={(e) => setWantsEngagement(e.target.checked)}
              className="mt-0.5"
            />
            <span>
              <span className="font-medium text-foreground">QUATA — engagement</span>
              <span className="block text-muted-foreground">
                Support, orders, delivery updates, promotions.
              </span>
            </span>
          </label>

          <label className="flex cursor-pointer items-start gap-2 rounded-xl border border-violet-200 bg-violet-50 p-3.5 text-xs">
            <input
              type="checkbox"
              checked={wantsAuth}
              onChange={(e) => setWantsAuth(e.target.checked)}
              className="mt-0.5"
            />
            <span>
              <span className="font-medium text-violet-900">
                Quata Verify — authentication
              </span>
              <span className="block text-violet-900/80">
                Security codes only. This is the number every login in the fleet depends
                on.
              </span>
            </span>
          </label>

          {granting && (
            <div className="grid gap-2 rounded-xl border-2 border-amber-300 bg-amber-50 p-3.5 text-xs text-amber-900">
              <div className="flex items-start gap-2">
                <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span>
                  Granting Quata Verify puts {product.name}&apos;s traffic beside the
                  fleet&apos;s OTP path. It is a separate, separately audited act with a
                  mandatory justification for exactly that reason. It still cannot send
                  anything but authentication templates there — the category rule is
                  enforced per template, not per product.
                </span>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="grant-justification">Why — required</Label>
                <Textarea
                  id="grant-justification"
                  rows={2}
                  value={justification}
                  onChange={(e) => setJustification(e.target.value)}
                  aria-invalid={justification.length > 0 && !justified}
                  placeholder="e.g. QuataPay is moving its login OTP from email back to WhatsApp, approved 2026-08-11"
                />
                <p className="text-[11px]">At least 8 characters.</p>
              </div>
            </div>
          )}

          {had && !wantsAuth && (
            <Note tone="warn">
              Removing Quata Verify means {product.name} can no longer request a
              security-code template. Any routing rule aimed at that number will start
              being refused. Re-granting it later needs a justification again.
            </Note>
          )}

          {selected.length === 0 && (
            <Note tone="warn">
              With no purpose granted this product can never send anything — every route
              would be refused. That is a valid way to stand it down, but disabling it
              is the usual one.
            </Note>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button
            onClick={submit}
            disabled={busy || unchanged || (granting && !justified) || selected.length === 0}
          >
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ------------------------------------------------------------ enablement */

function EnablementDialog({
  product,
  onClose,
  onConfirm,
  busy,
}: {
  product: QcpProductRegistryItem;
  onClose: () => void;
  onConfirm: () => void | Promise<void>;
  busy: boolean;
}) {
  const enabling = !product.is_enabled;

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {enabling ? "Enable" : "Disable"} {product.name}?
          </DialogTitle>
          <DialogDescription>
            {enabling
              ? "This is the per-product migration gate. It lets this product's calls reach QCP's sender at all."
              : "The product's calls will be refused before Meta is contacted, and recorded as suppressions."}
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-3">
          {enabling ? (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-3.5 text-xs text-amber-900">
              <div className="flex items-start gap-2">
                <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <div>
                  <p>
                    Enabling means <strong>{product.name}</strong> may ask QCP to send.
                    Whether anything actually leaves still depends on three other gates —
                    the environment switch, the delivery setting, and the number being
                    active — none of which this touches.
                  </p>
                  {!product.has_api_key && (
                    <p className="mt-2">
                      It has <strong>no API key</strong>, so it could not authenticate at
                      the gateway. QCP will refuse this: &ldquo;enabled&rdquo; would be a
                      claim the console makes and every request contradicts. Mint a key
                      first.
                    </p>
                  )}
                  {product.routing_rules_active === 0 && (
                    <p className="mt-2">
                      It has <strong>no active routing rule</strong>. Every send will be
                      refused with &ldquo;no rule for that intent&rdquo; until one
                      exists.
                    </p>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <Note>
              Its API key survives, so re-enabling is one click. Nothing about the
              product&apos;s templates or rules is touched.
            </Note>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button
            variant={enabling ? "default" : "destructive"}
            disabled={busy || (enabling && !product.has_api_key)}
            onClick={onConfirm}
          >
            {enabling ? "Enable product" : "Disable product"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ---------------------------------------------------------- show-once key */

/**
 * The only place in this console where a secret is rendered.
 *
 * It is the value the backend just generated, held in one piece of component
 * state and dropped when this closes. It is never put in a toast (toasts
 * linger and stack), never in the URL, never in browser storage, and it
 * cannot be recovered by reloading — the server kept only its sha256. Closing
 * the dialog is destructive, so the close control says so and asks for an
 * acknowledgement rather than accepting a reflex click.
 */
function MintedKeyDialog({
  minted,
  onClose,
}: {
  minted: QcpMintedKey;
  onClose: () => void;
}) {
  const [acknowledged, setAcknowledged] = React.useState("");

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>API key for {minted.product.name}</DialogTitle>
          <DialogDescription>
            This is the only time this value will ever be displayed.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-3">
          <div className="rounded-xl border-2 border-amber-400 bg-amber-50 p-3.5 text-xs text-amber-900">
            <div className="flex items-start gap-2">
              <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
              <div>
                <div className="text-sm font-semibold">
                  Copy it now. It will not be shown again.
                </div>
                <p className="mt-1">{minted.notice}</p>
                <p className="mt-1">
                  QCP stored only its sha256 digest, the prefix{" "}
                  <code>{minted.prefix}</code> and the fingerprint{" "}
                  <code>{minted.fingerprint}</code>. Nobody — not this console, not the
                  database, not support — can recover the value once this closes.
                </p>
              </div>
            </div>
          </div>

          <div className="grid gap-2">
            <Label htmlFor="minted-key">API key</Label>
            <div className="flex flex-wrap items-center gap-2">
              <code
                id="minted-key"
                className="min-w-0 flex-1 break-all rounded-lg border border-border bg-surface-soft p-3 text-xs"
              >
                {minted.api_key}
              </code>
              <CopyButton value={minted.api_key} label="Copy key" />
            </div>
            <p className="text-[11px] text-muted-foreground">
              Send it as <code>X-QCP-Key</code> alongside{" "}
              <code>X-QCP-Product: {minted.product.slug}</code>. Put it in the
              product&apos;s secret store, never in its repository.
            </p>
          </div>

          <TypeToConfirm
            phrase="stored it"
            value={acknowledged}
            onChange={setAcknowledged}
            label="Closing this discards the value permanently."
          />
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            disabled={acknowledged.trim() !== "stored it"}
            onClick={onClose}
          >
            Done — discard from this screen
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
