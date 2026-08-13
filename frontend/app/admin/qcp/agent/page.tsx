"use client";

/**
 * The QCP agent console — where a support person answers customers all day.
 *
 * This is a working screen, not a dashboard. Somebody in Bamenda has it open
 * for eight hours; everything on it is either something they act on or
 * something they must not get wrong. It is laid out in that order:
 *
 *  1. **The waiting queue, oldest first, with the wait set large.** A customer
 *     who has been waiting forty minutes is the reason this screen exists, and
 *     that has to be visible from across the room rather than inferred from a
 *     timestamp. An escalation nobody has picked up is marked as overdue,
 *     because an escalation nobody looks at is the same outcome as no
 *     escalation at all.
 *  2. **The thread, with who-said-what unmistakable.** Customer, Quata AI and
 *     a named human are three different voices in one transcript. An agent
 *     skim-reading while typing must never mistake the AI's words for the
 *     customer's, or their colleague's for their own.
 *  3. **The composer.** A draft is *asked for*, never pushed: nothing calls
 *     the AI when the screen loads, and nothing leaves this browser until a
 *     human presses Send.
 *  4. **Claim / release / hand back to AI**, because two agents answering one
 *     customer is worse than nobody answering.
 *  5. **The 24-hour window state**, stated in Meta's terms. When it has closed
 *     the agent physically cannot type, and if they do not understand *why*
 *     they will report the tool as broken and go around it.
 *
 * Two rules are enforced in code rather than by wording, because wording is not
 * a control (both live in `./api`):
 *
 *  * **Quata Verify is untouchable from here.** `verifyNumberLock` removes the
 *    composer, the template picker and the draft button — `visibleSuggestion`
 *    refuses to return a draft for such a thread even if the backend sent one.
 *    That number carries the fleet's security codes; nothing a support agent
 *    composes belongs on it.
 *  * **The AI's switches are honoured on the client too.** With drafting off,
 *    no draft is rendered and the button is gone. Human replies are untouched,
 *    which is the entire point of the switch.
 *
 * Empty is the normal state today. QCP ships dormant — no credentials, no
 * enabled product, nobody messaging — so an empty queue is *correct*, and the
 * screen says so in those words. A screen that looks broken when it is right
 * gets someone to "fix" a working system.
 */

import * as React from "react";
import Link from "next/link";
import {
  AlertTriangle,
  Bot,
  CheckCheck,
  Clock,
  CornerUpLeft,
  Hand,
  Headset,
  Inbox,
  Lock,
  RefreshCw,
  Send,
  ShieldAlert,
  Sparkles,
  TimerOff,
  User,
} from "lucide-react";
import { PageShell } from "@/components/admin/page-shell";
import { EmptyState } from "@/components/admin/empty-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { useApi } from "@/lib/use-api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { useQcpWrite, type QcpRefusal } from "../api";
import {
  Loading,
  LoadError,
  Note,
  PurposeBadge,
  QcpTabs,
  RefusalBanner,
  fmt,
  relative,
} from "../shared";
import {
  AGENT,
  canAskForDraft,
  canSendTemplate,
  clientToken,
  formatWait,
  handoverLabel,
  mergeQueues,
  replyBlockers,
  speakerName,
  speakerOf,
  verifyNumberLock,
  visibleSuggestion,
  waitMinutes,
  waitTone,
  type AgentAiState,
  type AgentMessage,
  type AgentQueue,
  type AgentQueueItem,
  type AgentSuggestion,
  type AgentTemplate,
  type AgentThread,
  type ReplyPayload,
  type WaitTone,
} from "./api";

/**
 * Who may work this console.
 *
 * Mirrors `conversations.WHATSAPP_AGENT_PERMISSIONS` on the backend: an agent
 * role can be entitled to answer customers without being entitled to
 * reconfigure the platform, so this is not gated on `settings:manage` alone the
 * way the rest of the QCP console is.
 */
const AGENT_PERMISSIONS = ["whatsapp:agent", "whatsapp:manage", "settings:manage"];

/** The queue is a live thing; poll it rather than making the agent press refresh. */
const QUEUE_POLL_MS = 15_000;
/** Wait times must age on screen without a round trip. */
const CLOCK_MS = 10_000;

export default function QcpAgentPage() {
  return (
    <PageShell
      title="Agent console"
      description="Customers waiting for a person, oldest first. Ask the AI for a draft if you want one; you decide whether it goes out."
    >
      <QcpTabs />
      <Gate>
        <AgentConsole />
      </Gate>
    </PageShell>
  );
}

/**
 * Permission gate.
 *
 * `PageShell` takes a single permission and this screen accepts any of three,
 * so the check is here. It is a copy of the shell's own refusal block on
 * purpose — an agent who lacks the entitlement should see the same sentence
 * they would see anywhere else in the cockpit.
 */
function Gate({ children }: { children: React.ReactNode }) {
  const { hasPermission } = useAuth();
  if (!AGENT_PERMISSIONS.some((p) => hasPermission(p))) {
    return (
      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-6 text-amber-900">
        You don&apos;t have permission to work the agent console. It needs the WhatsApp
        agent entitlement on your role.
      </div>
    );
  }
  return <>{children}</>;
}

/** A ticking clock, so a wait time ages without refetching anything. */
function useNow(intervalMs: number) {
  const [now, setNow] = React.useState(() => Date.now());
  React.useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(t);
  }, [intervalMs]);
  return now;
}

function AgentConsole() {
  const now = useNow(CLOCK_MS);
  const [selected, setSelected] = React.useState<number | null>(null);

  const waiting = useApi<AgentQueue>(AGENT.waiting);
  const mine = useApi<AgentQueue>(AGENT.mine);
  const thread = useApi<AgentThread>(selected ? AGENT.thread(selected) : null);

  // Poll the queues only. Refetching the open thread would wipe a half-typed
  // reply, which is a worse failure than a slightly stale transcript.
  const refresh = React.useRef(() => {
    waiting.refresh();
    mine.refresh();
  });
  React.useEffect(() => {
    refresh.current = () => {
      waiting.refresh();
      mine.refresh();
    };
  });
  React.useEffect(() => {
    const t = window.setInterval(() => refresh.current(), QUEUE_POLL_MS);
    return () => window.clearInterval(t);
  }, []);

  const ai: AgentAiState = thread.data?.ai ?? waiting.data?.ai ?? mine.data?.ai ?? {};
  const items = mergeQueues(
    waiting.data?.items ?? [],
    mine.data?.items ?? [],
    now
  );

  const refreshAll = () => {
    waiting.refresh();
    mine.refresh();
  };

  return (
    <div className="grid gap-4">
      <AiStateBanner ai={ai} />

      {waiting.error ? (
        <LoadError error={waiting.error} onRetry={refreshAll} />
      ) : waiting.loading && !waiting.data ? (
        <Loading label="Loading the queue…" />
      ) : (
        <div className="grid gap-4 xl:grid-cols-[minmax(0,24rem)_minmax(0,1fr)]">
          <QueuePanel
            items={items}
            now={now}
            selected={selected}
            onSelect={setSelected}
            onRefresh={refreshAll}
          />
          <ThreadPanel
            key={selected ?? "none"}
            conversationId={selected}
            data={thread.data}
            error={thread.error}
            loading={thread.loading}
            ai={ai}
            onRefresh={() => {
              thread.refresh();
              refreshAll();
            }}
          />
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------ AI switches */

/**
 * The state of the AI itself.
 *
 * Every state below is *normal* and each changes what the agent sees, so none
 * of them may be silent. If drafts stop appearing and nothing explains it, the
 * agent's first conclusion is that the screen is broken.
 */
function AiStateBanner({ ai }: { ai: AgentAiState }) {
  if (ai.enabled === undefined) return null;

  if (ai.kill_switch) {
    return (
      <div
        role="status"
        data-testid="ai-state"
        className="flex items-start gap-2 rounded-xl border border-rose-300 bg-rose-50 p-3.5 text-xs text-rose-900"
      >
        <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        <div className="min-w-0">
          <div className="text-sm font-semibold">AI replies are switched off</div>
          <p className="mt-1">
            The kill switch is on, so the AI is answering nobody by itself. You and
            every other agent can still read and reply normally — that is what the
            switch is for.
            {ai.suggestions_enabled
              ? " Drafting for you is a separate switch and is still on."
              : " Drafting for you is also off, so no suggested replies will appear."}
          </p>
        </div>
      </div>
    );
  }

  // Louder than "not configured", and checked first: an unconfigured AI hands
  // every thread to a person, which is a safe outcome. An AI that is on with
  // no routing rule composes replies that are then refused by the gateway —
  // the customer gets nothing and no screen said so.
  if (ai.misconfigured) {
    return (
      <div
        role="alert"
        data-testid="ai-state"
        className="flex items-start gap-2 rounded-xl border border-rose-300 bg-rose-50 p-3.5 text-xs text-rose-900"
      >
        <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        <div className="min-w-0">
          <div className="text-sm font-semibold">
            AI replies are on, but the AI can answer nobody
          </div>
          <p className="mt-1">
            {ai.blocker === "AI_BLOCKED_NO_PRODUCT" ? (
              <>No product is enabled, so there is nothing for the AI to answer for.</>
            ) : (
              <>
                There is no active <code>ai_support_reply</code> routing rule on the
                QUATA engagement number, so every reply the AI composes is refused
                before it is sent.
              </>
            )}
          </p>
          {ai.gaps && ai.gaps.length > 0 ? (
            <ul className="mt-1.5 list-disc space-y-0.5 pl-4">
              {ai.gaps.map((gap) => (
                <li key={gap.product}>
                  <span className="font-medium">{gap.product}</span> — missing in{" "}
                  {gap.locales.join(", ")}
                </li>
              ))}
            </ul>
          ) : null}
          <p className="mt-1.5">
            Fix it in{" "}
            <Link href="/admin/qcp/routing" className="underline underline-offset-2">
              QCP → Routing
            </Link>
            . A rule must exist for every language listed: one created for English
            alone answers anglophone customers and leaves every francophone customer
            unanswered.
          </p>
        </div>
      </div>
    );
  }

  if (!ai.configured) {
    return (
      <Note>
        AI replies are switched on but no model is configured, so every conversation
        is being handed to a person instead. Nobody is left unanswered — but nothing
        is being drafted either.
      </Note>
    );
  }

  if (!ai.suggestions_enabled) {
    return (
      <Note>
        AI drafting for agents is off. Threads still arrive here and you reply to them
        by hand; when it is switched on, a &ldquo;Ask the AI for a draft&rdquo; button
        appears on the reply box.
      </Note>
    );
  }
  return null;
}

/* ------------------------------------------------------------- the queue */

const WAIT_TONE_CLASS: Record<WaitTone, string> = {
  calm: "text-muted-foreground",
  warn: "text-amber-700",
  urgent: "text-rose-700",
};

const WAIT_ROW_CLASS: Record<WaitTone, string> = {
  calm: "",
  warn: "bg-amber-50/60",
  urgent: "bg-rose-50/70",
};

function QueuePanel({
  items,
  now,
  selected,
  onSelect,
  onRefresh,
}: {
  items: AgentQueueItem[];
  now: number;
  selected: number | null;
  onSelect: (id: number) => void;
  onRefresh: () => void;
}) {
  const longest = items.length ? waitMinutes(items[0], now) : null;
  const overdue = items.filter((i) => i.overdue).length;

  return (
    <div className="grid gap-2 self-start">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold tracking-tight">
          Waiting <span className="text-muted-foreground">({items.length})</span>
        </h3>
        {longest != null && longest >= 5 && (
          <Badge variant={longest >= 15 ? "danger" : "warn"}>
            <Clock className="h-3 w-3" /> longest {formatWait(longest)}
          </Badge>
        )}
        <Button
          variant="outline"
          size="sm"
          onClick={onRefresh}
          className="ml-auto"
          aria-label="Refresh queue"
        >
          <RefreshCw className="h-3.5 w-3.5" />
        </Button>
      </div>

      {overdue > 0 && (
        <div
          data-testid="overdue-banner"
          className="flex items-start gap-2 rounded-xl border border-rose-300 bg-rose-50 p-3 text-xs text-rose-900"
        >
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>
            <strong>
              {overdue} {overdue === 1 ? "person" : "people"} the AI handed over
            </strong>{" "}
            {overdue === 1 ? "has" : "have"} been waiting past the alert threshold and
            nobody has claimed {overdue === 1 ? "them" : "them"}.
          </span>
        </div>
      )}

      {items.length === 0 ? (
        <div className="grid gap-3">
          <EmptyState
            icon={Inbox}
            title="Nobody is waiting"
            description="Every customer who needs a person will appear here, oldest at the top."
          />
          <Note>
            QCP is dormant — no number is switched on and no product is enabled, so
            nobody can message it yet. An empty queue is the correct state today, not a
            fault.
          </Note>
        </div>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-border bg-card ring-soft divide-y divide-border">
          {items.map((c) => (
            <QueueRow
              key={c.conversation_id}
              item={c}
              now={now}
                active={selected === c.conversation_id}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function QueueRow({
  item,
  now,
  active,
  onSelect,
}: {
  item: AgentQueueItem;
  now: number;
  active: boolean;
  onSelect: (id: number) => void;
}) {
  const mins = waitMinutes(item, now);
  const tone = waitTone(mins);
  const handover = handoverLabel(item.handover_reason);

  return (
    <button
      data-testid="queue-row"
      onClick={() => onSelect(item.conversation_id)}
      className={cn(
        "flex w-full items-start gap-3 p-3.5 text-left transition-colors hover:bg-surface-soft/60",
        WAIT_ROW_CLASS[tone],
        active && "bg-brand-soft/40"
      )}
    >
      {/* The wait, set large. This is the number the room reads. */}
      <span
        data-testid="wait"
        data-tone={tone}
        className={cn(
          "w-16 shrink-0 text-2xl font-semibold tabular-nums leading-tight tracking-tight",
          WAIT_TONE_CLASS[tone]
        )}
      >
        {formatWait(mins)}
      </span>

      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-2">
          <span className="truncate text-sm font-medium">
            {item.display_name || item.phone_e164}
          </span>
          {(item.unread_count ?? 0) > 0 && (
            <Badge variant="brand" className="ml-auto shrink-0">
              {item.unread_count}
            </Badge>
          )}
        </span>

        <span className="mt-1 flex flex-wrap items-center gap-1.5">
          <PurposeBadge purpose={item.account_purpose ?? null} />
          {item.product && (
            <Badge variant="outline" className="text-[11px]">
              {item.product}
            </Badge>
          )}
          {handover && (
            <Badge variant="warn" className="text-[11px]">
              {handover}
            </Badge>
          )}
          {item.overdue && (
            <Badge variant="danger" className="text-[11px]">
              nobody has picked this up
            </Badge>
          )}
          {item.mine ? (
            <Badge variant="success" className="text-[11px]">
              yours
            </Badge>
          ) : (
            item.held_by && (
              <Badge variant="default" className="text-[11px]">
                {item.held_by}
              </Badge>
            )
          )}
        </span>

        {item.answerable === false && (
          <span className="mt-1 block truncate text-xs text-muted-foreground">
            Cannot be answered from here — {item.answerable_reason}
          </span>
        )}
      </span>
    </button>
  );
}

/* ------------------------------------------------------------- the thread */

function ThreadPanel({
  conversationId,
  data,
  error,
  loading,
  ai,
  onRefresh,
}: {
  conversationId: number | null;
  data: AgentThread | null;
  error: Error | null;
  loading: boolean;
  ai: AgentAiState;
  onRefresh: () => void;
}) {
  if (!conversationId) {
    return (
      <EmptyState
        icon={Headset}
        title="Pick someone from the queue"
        description="Their conversation opens here, with the reply box ready."
      />
    );
  }
  if (error) return <LoadError error={error} onRetry={onRefresh} />;
  if (loading && !data) return <Loading label="Opening the conversation…" />;

  const c = data?.conversation ?? null;
  if (!c)
    return <LoadError error={new Error("This thread came back empty")} onRetry={onRefresh} />;

  const customerLabel = c.display_name || c.phone_e164;
  const messages = data?.messages ?? [];
  const locked = verifyNumberLock(c);

  return (
    <div className="rounded-2xl border border-border bg-card ring-soft">
      <ThreadHeader
        conversation={c}
        conversationId={conversationId}
        onRefresh={onRefresh}
      />

      <div className="max-h-[30rem] overflow-y-auto p-4">
        {messages.length === 0 ? (
          <EmptyState
            icon={Inbox}
            title="Nothing has been said yet"
            description="This conversation exists but carries no messages."
          />
        ) : (
          <div className="grid gap-3">
            {messages.map((m) => (
              <Bubble key={m.id} message={m} customerLabel={customerLabel} />
            ))}
          </div>
        )}
      </div>

      {locked ? (
        <VerifyLock reason={locked} />
      ) : (
        <Composer
          conversationId={conversationId}
          conversation={c}
          templates={data?.templates ?? []}
          ai={ai}
          onSent={onRefresh}
        />
      )}
    </div>
  );
}

function ThreadHeader({
  conversation: c,
  conversationId,
  onRefresh,
}: {
  conversation: AgentQueueItem;
  conversationId: number;
  onRefresh: () => void;
}) {
  const { write, busy } = useQcpWrite();
  const toast = useToast();

  async function act(path: string, ok: string) {
    const res = await write(path, { method: "POST" });
    if (!res.ok) {
      toast.error(res.refusal.title, res.refusal.detail);
      return;
    }
    toast.success(ok);
    onRefresh();
  }

  return (
    <div className="border-b border-border p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-base font-semibold tracking-tight">
          {c.display_name || c.phone_e164}
        </span>
        <PurposeBadge purpose={c.account_purpose ?? null} />
        {c.product && <Badge variant="outline">{c.product}</Badge>}
        {c.mine ? (
          <Badge variant="success">Yours</Badge>
        ) : c.held_by ? (
          <Badge variant="default">With {c.held_by}</Badge>
        ) : (
          <Badge variant="warn">Unclaimed</Badge>
        )}

        <div className="ml-auto flex flex-wrap items-center gap-2">
          {c.mine ? (
            <>
              <Button
                variant="outline"
                size="sm"
                disabled={busy}
                onClick={() => act(AGENT.release(conversationId), "Released back to the queue")}
              >
                Release
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={busy}
                onClick={() => act(AGENT.returnToAi(conversationId), "Handed back to the AI")}
              >
                <CornerUpLeft className="h-3.5 w-3.5" /> Hand back to AI
              </Button>
            </>
          ) : (
            !c.held_by && (
              <Button
                size="sm"
                disabled={busy}
                onClick={() => act(AGENT.claim(conversationId), "Claimed")}
              >
                <Hand className="h-3.5 w-3.5" /> Claim
              </Button>
            )
          )}
          <Button variant="outline" size="sm" onClick={onRefresh} aria-label="Refresh thread">
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      <div className="mt-1.5 text-xs text-muted-foreground">
        {c.phone_e164} · on {c.account ?? "unknown number"} · last heard from{" "}
        {relative(c.last_inbound_at)}
      </div>

      {c.escalated && (
        <p className="mt-1.5 text-[11px] font-medium text-amber-800">
          The AI handed this over
          {handoverLabel(c.handover_reason) ? `: ${handoverLabel(c.handover_reason)}` : ""} —
          it is waiting for a person, not for a bot.
        </p>
      )}

      <WindowState conversation={c} />
    </div>
  );
}

/**
 * The 24-hour window, stated where the agent will look for it.
 *
 * Open, this is a quiet line. Closed, it is the single most important thing on
 * the screen after the transcript, because it is the difference between "the
 * reply box is broken" and "Meta will not carry a free-form message to this
 * person until they write again".
 */
function WindowState({ conversation: c }: { conversation: AgentQueueItem }) {
  if (c.service_window_open) {
    return (
      <p className="mt-1.5 text-[11px] text-muted-foreground">
        <CheckCheck className="mr-1 inline h-3 w-3" />
        You can reply freely until {fmt(c.service_window_expires_at)} — Meta&apos;s
        24-hour service window is open.
      </p>
    );
  }
  // Deliberately short. The full explanation lives on the composer, which is
  // where the agent actually discovers they cannot type; saying it twice on one
  // screen trains people to skim past both.
  return (
    <p className="mt-1.5 flex items-start gap-1.5 text-[11px] font-medium text-amber-800">
      <TimerOff className="mt-0.5 h-3 w-3 shrink-0" />
      <span>
        Meta&apos;s 24-hour window closed {fmt(c.service_window_expires_at)} — only an
        approved template can go out. See the reply box.
      </span>
    </p>
  );
}

/* ------------------------------------------------------------- transcript */

const SPEAKER_STYLE = {
  customer: {
    row: "justify-start",
    box: "border-border bg-surface-soft",
    name: "text-foreground",
    icon: User,
  },
  ai: {
    // Dashed and violet: machine-authored, and never confusable with a colleague.
    row: "justify-end",
    box: "border-dashed border-violet-300 bg-violet-50",
    name: "text-violet-900",
    icon: Bot,
  },
  agent: {
    row: "justify-end",
    box: "border-primary/25 bg-brand-soft/50",
    name: "text-foreground",
    icon: Headset,
  },
  automation: {
    row: "justify-end",
    box: "border-border bg-surface",
    name: "text-muted-foreground",
    icon: Sparkles,
  },
} as const;

function Bubble({
  message: m,
  customerLabel,
}: {
  message: AgentMessage;
  customerLabel: string;
}) {
  const speaker = speakerOf(m);
  const style = SPEAKER_STYLE[speaker];
  const Icon = style.icon;

  return (
    <div data-testid="bubble" data-speaker={speaker} className={cn("flex", style.row)}>
      <div className={cn("max-w-[85%] rounded-2xl border px-3.5 py-2.5", style.box)}>
        <div
          className={cn(
            "flex flex-wrap items-center gap-1.5 text-[11px] font-medium",
            style.name
          )}
        >
          <Icon className="h-3 w-3" />
          {speakerName(m, customerLabel)}
          {m.kind === "template" && (
            <Badge variant="outline" className="text-[10px]">
              template
            </Badge>
          )}
        </div>

        <div className="mt-1 whitespace-pre-wrap break-words text-sm">
          {m.body || <span className="italic text-muted-foreground">No body stored</span>}
        </div>

        <div className="mt-2 text-[11px] text-muted-foreground">
          {fmt(m.created_at)}
          {m.status && m.direction === "outbound" ? ` · ${m.status}` : ""}
          {m.suppressed_reason ? ` · ${m.suppressed_reason}` : ""}
        </div>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------- composer */

/** Quata Verify: no composer at all, and the reason in full. */
function VerifyLock({ reason }: { reason: string }) {
  return (
    <div className="border-t border-border p-4">
      <div className="flex items-start gap-2 rounded-xl border border-violet-300 bg-violet-50 p-3.5 text-xs text-violet-900">
        <Lock className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        <div className="min-w-0">
          <div className="text-sm font-semibold">This conversation is on Quata Verify</div>
          <p className="mt-1">{reason}</p>
        </div>
      </div>
    </div>
  );
}

function Composer({
  conversationId,
  conversation: c,
  templates,
  ai,
  onSent,
}: {
  conversationId: number;
  conversation: AgentQueueItem;
  templates: AgentTemplate[];
  ai: AgentAiState;
  onSent: () => void;
}) {
  const { write, busy } = useQcpWrite();
  const toast = useToast();

  const [text, setText] = React.useState("");
  const [suggestion, setSuggestion] = React.useState<AgentSuggestion | null>(null);
  const [refusal, setRefusal] = React.useState<QcpRefusal | null>(null);

  const blockers = replyBlockers(c);
  const blocking = blockers[0] ?? null;
  const freeFormAllowed = blockers.length === 0;
  const templateAllowed = canSendTemplate(c);
  const shown = visibleSuggestion(c, suggestion, ai);
  const draft = shown?.draft ?? "";
  const edited = Boolean(draft) && text !== draft;

  async function askForDraft() {
    setRefusal(null);
    const res = await write<AgentSuggestion>(AGENT.suggest(conversationId), {
      method: "POST",
    });
    if (!res.ok) {
      setRefusal(res.refusal);
      return;
    }
    setSuggestion(res.data);
    // Only a served draft goes into the box. An escalation carries no body at
    // all from the backend, and it must not become one here.
    if (res.data.draft && !res.data.escalate) setText(res.data.draft);
  }

  async function send(payload: ReplyPayload) {
    setRefusal(null);
    const res = await write(AGENT.reply(conversationId), { method: "POST", body: payload });
    if (!res.ok) {
      setRefusal(res.refusal);
      return;
    }
    toast.success("Reply sent");
    setText("");
    setSuggestion(null);
    onSent();
  }

  return (
    <div className="grid gap-3 border-t border-border p-4">
      {refusal && <RefusalBanner refusal={refusal} onDismiss={() => setRefusal(null)} />}

      {blocking && (
        <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <div className="min-w-0">
            <div className="text-sm font-semibold">{blocking.title}</div>
            <p className="mt-1">{blocking.detail}</p>
          </div>
        </div>
      )}

      {shown && <SuggestionStrip suggestion={shown} edited={edited} />}

      <div className="grid gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Label htmlFor="reply-body">
            {draft ? "Suggested draft — edit it or write your own" : "Your reply"}
          </Label>
          {canAskForDraft(c, ai) && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="ml-auto"
              data-testid="ask-for-draft"
              disabled={busy}
              onClick={askForDraft}
            >
              <Sparkles className="h-3.5 w-3.5" /> Ask the AI for a draft
            </Button>
          )}
        </div>
        <Textarea
          id="reply-body"
          data-testid="reply-body"
          rows={4}
          value={text}
          disabled={!freeFormAllowed || busy}
          onChange={(e) => setText(e.target.value)}
          placeholder={
            freeFormAllowed
              ? "Type your reply to the customer…"
              : "You cannot type a reply on this thread — see above."
          }
          className={cn(draft && !edited && "border-dashed border-violet-300 bg-violet-50/40")}
        />
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-[11px] text-muted-foreground">
            Nothing is sent until you press Send.
            {edited && " You have edited the draft."}
          </p>
          <Button
            className="ml-auto"
            disabled={!freeFormAllowed || busy || !text.trim()}
            onClick={() =>
              send({
                kind: "text",
                body: text.trim(),
                client_token: clientToken(),
                from_suggestion: Boolean(draft),
                suggestion_edited: edited,
              })
            }
          >
            <Send className="h-3.5 w-3.5" /> Send reply
          </Button>
        </div>
      </div>

      {c.service_window_open === false && templateAllowed && (
        <TemplateSend templates={templates} busy={busy} onSend={(p) => send(p)} />
      )}
    </div>
  );
}

/**
 * The AI's draft, labelled as a proposal.
 *
 * The visual weight here is doing real work: an agent who reads the pre-filled
 * box as "already sent" will not send the reply, and the customer waits twice.
 */
function SuggestionStrip({
  suggestion,
  edited,
}: {
  suggestion: AgentSuggestion;
  edited: boolean;
}) {
  if (suggestion.escalate || !suggestion.draft) {
    return (
      <div
        data-testid="suggestion-escalated"
        className="flex items-start gap-2 rounded-xl border border-violet-200 bg-violet-50 p-3 text-xs text-violet-900"
      >
        <Bot className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        <div className="min-w-0">
          <div className="text-sm font-semibold">The AI did not draft a reply</div>
          <p className="mt-1">
            {handoverLabel(suggestion.reason)
              ? `It handed this over: ${handoverLabel(suggestion.reason)}.`
              : "It handed this conversation over rather than answering."}{" "}
            Anything touching money, KYC, fraud, a complaint, a legal threat or an upset
            customer is a person&apos;s job.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      data-testid="suggestion"
      className="rounded-xl border border-dashed border-violet-300 bg-violet-50 p-3 text-xs text-violet-900"
    >
      <div className="flex flex-wrap items-center gap-2">
        <Sparkles className="h-3.5 w-3.5 shrink-0" />
        <span className="text-sm font-semibold">AI suggested draft — not sent</span>
        {edited && (
          <Badge variant="outline" className="border-violet-300 text-[10px]">
            edited by you
          </Badge>
        )}
        <span className="ml-auto text-[11px] text-violet-700">
          {[suggestion.model, suggestion.prompt_version && `prompt ${suggestion.prompt_version}`]
            .filter(Boolean)
            .join(" · ")}
        </span>
      </div>
      <p className="mt-1.5">
        This draft states no figures from any product API — the console read none, so it
        could not have. If it names a balance, a payment, a refund, an order total or an
        account status, do not send it: look the value up and type it yourself.
      </p>
    </div>
  );
}

/**
 * The only thing that can go out once the window has closed.
 *
 * Rendered next to the explanation rather than on some other screen, because
 * the moment an agent needs this is the moment they discover they cannot type.
 */
function TemplateSend({
  templates,
  busy,
  onSend,
}: {
  templates: AgentTemplate[];
  busy: boolean;
  onSend: (payload: ReplyPayload) => void;
}) {
  const [intent, setIntent] = React.useState("");
  const [vars, setVars] = React.useState<Record<string, string>>({});
  const chosen = templates.find((t) => t.intent === intent) ?? null;
  const needed = chosen?.variables ?? [];

  return (
    <div
      data-testid="template-picker"
      className="grid gap-2 rounded-xl border border-border bg-surface-soft p-3"
    >
      <Label htmlFor="reply-template" className="text-xs">
        Approved template
      </Label>
      {templates.length === 0 ? (
        <p className="text-[11px] text-muted-foreground">
          No approved template is available for this number yet, so this customer cannot
          be reached until they message again. Ask an administrator to submit one on the
          Templates tab.
        </p>
      ) : (
        <>
          <Select
            id="reply-template"
            value={intent}
            onChange={(e) => {
              setIntent(e.target.value);
              setVars({});
            }}
          >
            <option value="">— Choose a template —</option>
            {templates.map((t) => (
              <option key={t.intent} value={t.intent}>
                {t.name}
                {t.language ? ` (${t.language})` : ""}
              </option>
            ))}
          </Select>

          {needed.map((v) => (
            <div key={v} className="grid gap-1">
              <Label htmlFor={`tplvar-${v}`} className="text-[11px]">
                {`{{${v}}}`}
              </Label>
              <Input
                id={`tplvar-${v}`}
                value={vars[v] ?? ""}
                onChange={(e) => setVars((p) => ({ ...p, [v]: e.target.value }))}
              />
            </div>
          ))}

          <Button
            size="sm"
            className="justify-self-end"
            disabled={busy || !chosen || needed.some((v) => !(vars[v] ?? "").trim())}
            onClick={() =>
              chosen &&
              onSend({
                kind: "template",
                intent: chosen.intent,
                // Positional, in the order the template declares them — which
                // is what `dispatch.send` takes.
                variables: needed.map((v) => vars[v] ?? ""),
                client_token: clientToken(),
              })
            }
          >
            <Send className="h-3.5 w-3.5" /> Send template
          </Button>
        </>
      )}
    </div>
  );
}
