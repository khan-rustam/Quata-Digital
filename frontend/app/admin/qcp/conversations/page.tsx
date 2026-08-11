"use client";

/**
 * QCP conversations — the agent console.
 *
 * Left: the inbox, filterable by product and state. Right: the selected
 * thread, oldest at the top, with the delivery state of every outbound
 * message and the redaction already applied at write time (an OTP is stored
 * as a digest, never in clear — what you see here is what exists).
 *
 * Inbound to the Verify number is normal and does create a thread: Meta will
 * deliver whatever a user types at it. What is forbidden is *sending*
 * free-form from that number, which the database refuses outright.
 *
 * The one write here is **reassignment**. An inbound message arrives with no
 * product attribution whenever QCP has no outbound row to tie it to — a user
 * replying to a number for the first time, or replying after the linking
 * message aged out. Until now a human could read such a thread and had no way
 * to route it, so nobody owned it and the customer was simply never answered.
 * Reassigning attributes the thread to a product; it does not send anything.
 */

import * as React from "react";
import { HelpCircle, Inbox, MessageSquare, RefreshCw, UserPlus } from "lucide-react";
import { PageShell } from "@/components/admin/page-shell";
import { EmptyState } from "@/components/admin/empty-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import { useToast } from "@/components/ui/toast";
import { SearchInput, useDebouncedValue } from "@/components/admin/search-input";
import { Pagination } from "@/components/admin/pagination";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";
import { QCP, useQcpWrite, type QcpRefusal } from "../api";
import {
  Loading,
  LoadError,
  MESSAGE_STATUS_TONE,
  Note,
  PurposeBadge,
  QcpTabs,
  RefusalBanner,
  StatusBadge,
  fmt,
  relative,
  type QcpConversation,
  type QcpMessage,
  type QcpOverview,
  type QcpProduct,
} from "../shared";

type ListResponse = {
  total: number;
  page: number;
  page_size: number;
  items: QcpConversation[];
};

type DetailResponse = {
  conversation: QcpConversation;
  messages: QcpMessage[];
  next_before_id: number | null;
};

export default function QcpConversationsPage() {
  return (
    <PageShell
      title="QCP conversations"
      description="Every WhatsApp thread across both numbers and every product. Message bodies are stored redacted — an OTP is a digest here because it is a digest in the database."
      requirePermission="settings:manage"
    >
      <QcpTabs />
      <Conversations />
    </PageShell>
  );
}

function Conversations() {
  const [product, setProduct] = React.useState("");
  const [state, setState] = React.useState("");
  const [search, setSearch] = React.useState("");
  const [page, setPage] = React.useState(1);
  const [selected, setSelected] = React.useState<number | null>(null);
  const debounced = useDebouncedValue(search);

  // Product options come from the registry, so the filter can never offer a
  // product that does not exist.
  const overview = useApi<QcpOverview>("/admin/qcp/overview");

  const params = new URLSearchParams({ page: String(page), page_size: "25" });
  if (product) params.set("product", product);
  if (state) params.set("state", state);
  if (debounced.trim()) params.set("q", debounced.trim());

  const { data, error, loading, refresh } = useApi<ListResponse>(
    `/admin/qcp/conversations?${params.toString()}`
  );

  const filtersActive = Boolean(product || state || debounced.trim());

  // Changing a filter must return to page 1 — page 4 of the old result set is
  // usually empty in the new one, which reads as "no conversations".
  function onFilterChange(apply: () => void) {
    apply();
    setPage(1);
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <SearchInput
          value={search}
          onChange={(v) => onFilterChange(() => setSearch(v))}
          placeholder="Search phone or name…"
        />
        <Select
          value={product}
          onChange={(e) => onFilterChange(() => setProduct(e.target.value))}
          className="w-auto"
          aria-label="Filter by product"
        >
          <option value="">All products</option>
          {(overview.data?.products ?? []).map((p) => (
            <option key={p.slug} value={p.slug}>
              {p.name}
            </option>
          ))}
        </Select>
        <Select
          value={state}
          onChange={(e) => onFilterChange(() => setState(e.target.value))}
          className="w-auto"
          aria-label="Filter by status"
        >
          <option value="">All states</option>
          <option value="open">Open</option>
          <option value="snoozed">Snoozed</option>
          <option value="closed">Closed</option>
        </Select>
        <Button variant="outline" size="sm" onClick={refresh} className="ml-auto">
          <RefreshCw className="h-3.5 w-3.5" /> Refresh
        </Button>
      </div>

      {error ? (
        <LoadError error={error} onRetry={refresh} />
      ) : loading && !data ? (
        <Loading label="Loading conversations…" />
      ) : (data?.items.length ?? 0) === 0 ? (
        filtersActive ? (
          <EmptyState
            icon={Inbox}
            title="No conversations match these filters"
            description="Clear the filters to see every thread."
            action={
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  onFilterChange(() => {
                    setProduct("");
                    setState("");
                    setSearch("");
                  })
                }
              >
                Clear filters
              </Button>
            }
          />
        ) : (
          <div className="grid gap-3">
            <EmptyState
              icon={Inbox}
              title="No conversations yet"
              description="A thread is created the first time someone messages one of the two numbers, or the first time QCP sends to a new contact."
            />
            <Note>
              With QCP dormant this is the expected state — no product is enabled, so
              nothing has been sent, and no number is active to receive.
            </Note>
          </div>
        )
      ) : (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
          <div>
            <div className="overflow-hidden rounded-2xl border border-border bg-card ring-soft divide-y divide-border">
              {data!.items.map((c) => (
                <button
                  key={c.id}
                  onClick={() => setSelected(c.id)}
                  className={cn(
                    "block w-full p-4 text-left transition-colors hover:bg-surface-soft/60",
                    selected === c.id && "bg-brand-soft/40"
                  )}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium truncate">
                      {c.display_name || c.phone_e164}
                    </span>
                    {c.unread_count > 0 && (
                      <Badge variant="brand" className="ml-auto shrink-0">
                        {c.unread_count}
                      </Badge>
                    )}
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-1.5">
                    <PurposeBadge purpose={c.account_purpose} />
                    {c.product ? (
                      <Badge variant="outline" className="text-[11px]">
                        {c.product}
                      </Badge>
                    ) : (
                      /* Nobody owns this thread, so nobody answers it. That
                         is the state the reassign action exists to end. */
                      <Badge variant="warn" className="text-[11px]">
                        <HelpCircle className="h-3 w-3" /> Unattributed
                      </Badge>
                    )}
                    <Badge
                      variant={c.state === "open" ? "success" : "default"}
                      className="text-[11px]"
                    >
                      {c.state}
                    </Badge>
                  </div>
                  <div className="mt-1.5 text-xs text-muted-foreground">
                    {c.phone_e164} · last inbound {relative(c.last_inbound_at)}
                  </div>
                </button>
              ))}
            </div>
            <Pagination
              page={data!.page}
              pageSize={data!.page_size}
              total={data!.total}
              onPageChange={setPage}
            />
          </div>

          <Thread
            conversationId={selected}
            products={overview.data?.products ?? []}
            onChanged={refresh}
          />
        </div>
      )}
    </div>
  );
}

/* --------------------------------------------------------------- thread */

function Thread({
  conversationId,
  products,
  onChanged,
}: {
  conversationId: number | null;
  products: QcpProduct[];
  onChanged: () => void;
}) {
  const { data, error, loading, refresh } = useApi<DetailResponse>(
    conversationId ? `/admin/qcp/conversations/${conversationId}` : null
  );
  const [reassigning, setReassigning] = React.useState(false);

  if (!conversationId) {
    return (
      <EmptyState
        icon={MessageSquare}
        title="Pick a conversation"
        description="Select a thread on the left to read it and see the delivery state of every message."
      />
    );
  }
  if (error) return <LoadError error={error} onRetry={refresh} />;
  if (loading || !data) return <Loading label="Loading thread…" />;

  const c = data.conversation;
  // The API returns newest-first (keyset paged on id); read it oldest-first.
  const messages = [...data.messages].reverse();

  return (
    <div className="rounded-2xl border border-border bg-card ring-soft">
      <div className="border-b border-border p-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-base font-semibold tracking-tight">
            {c.display_name || c.phone_e164}
          </span>
          <PurposeBadge purpose={c.account_purpose} />
          {c.product ? (
            <Badge variant="outline">{c.product}</Badge>
          ) : (
            <Badge variant="warn">
              <HelpCircle className="h-3 w-3" /> Unattributed
            </Badge>
          )}
          <Badge variant={c.state === "open" ? "success" : "default"}>{c.state}</Badge>
          <div className="ml-auto flex items-center gap-2">
            {/* Only offered where it can succeed. QCP fills in a blank owner
                and never takes a live thread from the product working it, so
                an owned thread has no reassign action — see the note below. */}
            {!c.product && (
              <Button size="sm" onClick={() => setReassigning(true)}>
                <UserPlus className="h-3.5 w-3.5" /> Assign to a product
              </Button>
            )}
            <Button variant="outline" size="sm" onClick={refresh}>
              <RefreshCw className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
        <div className="mt-1.5 text-xs text-muted-foreground">
          {c.phone_e164} · on {c.account_name ?? c.account ?? "unknown number"} ·{" "}
          {c.service_window_open
            ? `free-form window open until ${fmt(c.service_window_expires_at)}`
            : "free-form window closed — only approved templates can be sent"}
        </div>

        {!c.product ? (
          <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
            <div className="flex items-start gap-2">
              <HelpCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>
                <strong>Nobody owns this thread.</strong> Four products share this
                number, so when a reply cannot be tied to an outbound message QCP
                attributes it to nobody rather than guessing — guessing hands one
                company&apos;s customer to another. Nothing routes an unowned thread, so
                nothing will answer it. Assign it and it enters that product&apos;s
                queue, along with the inbound messages nobody claimed.
              </span>
            </div>
          </div>
        ) : (
          <p className="mt-2 text-[11px] text-muted-foreground">
            Owned by <strong>{c.product}</strong>. QCP only ever fills in a blank owner
            — it will not move a live thread away from the product working it.
          </p>
        )}
      </div>

      <div className="max-h-[32rem] overflow-y-auto p-4">
        {messages.length === 0 ? (
          <EmptyState
            icon={MessageSquare}
            title="No messages in this thread"
            description="The conversation exists but carries no message rows yet."
          />
        ) : (
          <div className="grid gap-3">
            {messages.map((m) => (
              <Bubble key={m.id} message={m} />
            ))}
          </div>
        )}
      </div>

      {reassigning && (
        <ReassignDialog
          key={c.id}
          conversation={c}
          products={products}
          onClose={() => setReassigning(false)}
          onSaved={() => {
            refresh();
            onChanged();
          }}
        />
      )}
    </div>
  );
}

/* ------------------------------------------------------------- reassign */

/**
 * Attribute a thread to a product.
 *
 * This is the smallest possible write and deliberately so: it changes who
 * owns the conversation, nothing else. It sends no message, does not reopen a
 * closed thread, and cannot move the thread to the other number — a
 * conversation belongs to the account the contact actually messaged, and
 * pretending otherwise would put a reply on the wrong sender.
 *
 * Products that may not reach this thread's number are still listed, but
 * flagged: attributing the thread to one of them is legal (it is just
 * ownership) while replying from it would be refused, and an operator picking
 * blind would find that out only when their reply vanished.
 */
function ReassignDialog({
  conversation,
  products,
  onClose,
  onSaved,
}: {
  conversation: QcpConversation;
  products: QcpProduct[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const { write, busy } = useQcpWrite();
  const toast = useToast();
  const [product, setProduct] = React.useState(conversation.product ?? "");
  const [reason, setReason] = React.useState("");
  const [refusal, setRefusal] = React.useState<QcpRefusal | null>(null);

  const purpose = conversation.account_purpose;
  const chosen = products.find((p) => p.slug === product) ?? null;
  const reachable =
    !chosen || !purpose || (chosen.allowed_purposes ?? []).includes(purpose);

  async function submit() {
    setRefusal(null);
    const res = await write<{ messages_attributed?: number }>(
      QCP.conversationReassign(conversation.id),
      {
        method: "POST",
        body: {
          product,
          ...(reason.trim() ? { reason: reason.trim() } : {}),
        },
      }
    );
    if (!res.ok) {
      setRefusal(res.refusal);
      return;
    }
    const claimed = res.data?.messages_attributed ?? 0;
    toast.success(
      `Assigned to ${chosen?.name ?? product}`,
      claimed > 0
        ? `${conversation.phone_e164} and its ${claimed} unattributed inbound message${
            claimed === 1 ? "" : "s"
          } now belong to that product.`
        : `${conversation.phone_e164} now belongs to that product.`
    );
    onSaved();
    onClose();
  }

  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Assign {conversation.phone_e164} to a product</DialogTitle>
          <DialogDescription>
            Hands this thread, and the inbound messages nobody claimed, to one product.
            Nothing is sent to the contact.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-3">
          {refusal && (
            <RefusalBanner refusal={refusal} onDismiss={() => setRefusal(null)} />
          )}

          {conversation.product && (
            <RefusalBanner
              refusal={{
                title: `Already owned by ${conversation.product}`,
                detail:
                  "QCP only ever fills in a blank owner; it never takes a live thread from the product already working it. That rule is what stops one company's customer being handed to another. To move this, the owning product has to close the thread.",
                policy: true,
              }}
            />
          )}

          <div className="grid gap-2">
            <Label htmlFor="reassign-product">Owning product</Label>
            <Select
              id="reassign-product"
              value={product}
              disabled={!!conversation.product}
              onChange={(e) => setProduct(e.target.value)}
            >
              <option value="">— Choose a product —</option>
              {products.map((p) => (
                <option key={p.slug} value={p.slug}>
                  {p.name}
                  {p.is_enabled ? "" : " (disabled)"}
                </option>
              ))}
            </Select>
            {products.length === 0 && (
              <p className="text-[11px] text-muted-foreground">
                No products are registered, so there is nobody to hand this to. Register
                one on the Registry tab.
              </p>
            )}
          </div>

          {!reachable && chosen && (
            <Note tone="warn">
              {chosen.name} is not allowed to reach the{" "}
              {purpose === "authentication" ? "Quata Verify" : "QUATA"} number this
              thread is on. Ownership will be recorded, but any reply sent as that
              product would be refused. Grant the purpose on the Registry tab if
              replying is the point.
            </Note>
          )}

          {chosen && !chosen.is_enabled && (
            <Note tone="warn">
              {chosen.name} is disabled, so it cannot call QCP. The thread will sit in
              its queue unanswered until the product is enabled.
            </Note>
          )}

          <div className="grid gap-2">
            <Label htmlFor="reassign-reason">Why (recorded in the audit log)</Label>
            <Textarea
              id="reassign-reason"
              rows={2}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. customer is asking about a QuataFood order"
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button
            onClick={submit}
            disabled={busy || !product || !!conversation.product}
          >
            Assign
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Bubble({ message: m }: { message: QcpMessage }) {
  const inbound = m.direction === "inbound";
  const variables = Object.entries(m.variables ?? {});

  return (
    <div className={cn("flex", inbound ? "justify-start" : "justify-end")}>
      <div
        className={cn(
          "max-w-[85%] rounded-2xl border px-3.5 py-2.5",
          inbound
            ? "border-border bg-surface-soft"
            : "border-primary/25 bg-brand-soft/50"
        )}
      >
        <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
          <span className="uppercase tracking-wider">{m.kind}</span>
          {m.intent && <code>{m.intent}</code>}
          {m.product && <span>· {m.product}</span>}
        </div>

        <div className="mt-1 text-sm break-words whitespace-pre-wrap">
          {m.body || <span className="text-muted-foreground italic">No body stored</span>}
        </div>

        {variables.length > 0 && (
          <div className="mt-2 grid gap-0.5 rounded-lg bg-surface/70 p-2 text-[11px] text-muted-foreground">
            {variables.map(([k, v]) => (
              <div key={k} className="break-words">
                <span className="font-medium text-foreground">{k}</span>: {String(v)}
              </div>
            ))}
          </div>
        )}

        <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
          {!inbound && <StatusBadge value={m.status} tones={MESSAGE_STATUS_TONE} />}
          <span>{fmt(m.created_at)}</span>
          {m.attempts > 0 && (
            <span>
              · attempt {m.attempts}/{m.max_attempts}
            </span>
          )}
        </div>

        {(m.last_error || m.suppressed_reason) && (
          <div className="mt-1.5 text-[11px] text-rose-700 break-words">
            {m.suppressed_reason
              ? `Suppressed: ${m.suppressed_reason}`
              : m.last_error}
            {m.error_code && ` (code ${m.error_code})`}
          </div>
        )}
      </div>
    </div>
  );
}
