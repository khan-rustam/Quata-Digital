"use client";

/**
 * The agent console's entire knowledge of the AI-support backend.
 *
 * Every route, field name and safety predicate the screen uses lives here, so
 * a contract change is a diff to this file rather than a sweep through the
 * page. The shapes below are the real ones — `app/api/routes_admin_agent.py`
 * and `app/schemas/whatsapp_agent.py` — not a sketch of them.
 *
 * Two consequences, both deliberate:
 *
 * 1. **Every field the screen consumes is optional-tolerant.** A payload
 *    missing `handover_reason` renders a slightly emptier screen; it does not
 *    throw in front of an agent who has a customer waiting.
 * 2. **The safety rules are predicates in this module, not markup in the
 *    page.** `verifyNumberLock`, `replyBlockers` and `visibleSuggestion` are
 *    the enforcement points. The page cannot send, and cannot even render an
 *    AI draft, except through them.
 *
 * One backend decision shapes this whole file: **no response carries a staff
 * id.** Ownership arrives as `mine: boolean` and, for somebody else's thread,
 * a display name in `held_by`. So the console never compares user ids, and
 * cannot leak one to a product by accident.
 *
 * The rules the predicates exist to hold, in the order they matter:
 *
 * - **Nothing this screen does may put a message on Quata Verify.** That
 *   number carries security codes for four products. The AI must never draft
 *   for it and this console must never offer a send control on it — the
 *   backend and the database both refuse it too, and that is exactly why the
 *   UI must not be the layer that discovers the refusal.
 * - **A draft is not a message.** It is asked for explicitly, it is editable,
 *   and it exists nowhere but this browser until a human presses Send.
 * - **Free-form only inside Meta's 24-hour service window.** Outside it only
 *   an approved template can go out. The gateway enforces this; the console's
 *   job is to make the agent understand *why* they cannot type, so they don't
 *   conclude the tool is broken and go looking for someone to "fix" it.
 */

/* ----------------------------------------------------------------- paths */

const enc = encodeURIComponent;

/**
 * Endpoint map. One object, so a moved route is one edit.
 */
export const AGENT = {
  /** Waiting on any human: unassigned, not closed, a customer has written. */
  waiting: "/admin/qcp/agent/queue/unassigned",
  /** Threads assigned to me. */
  mine: "/admin/qcp/agent/queue",
  /** Escalations nobody has picked up. `?overdue_only=true` narrows it. */
  escalations: "/admin/qcp/agent/queue/escalations",
  /** One thread: conversation, messages, AI state, sendable templates. */
  thread: (id: number) => `/admin/qcp/agent/conversations/${enc(String(id))}/thread`,
  /** Take the thread. Guarded `WHERE assignee_id IS NULL` on the server. */
  claim: (id: number) => `/admin/qcp/agent/conversations/${enc(String(id))}/claim`,
  /** Put it back in the human queue without handing it to the AI. */
  release: (id: number) => `/admin/qcp/agent/conversations/${enc(String(id))}/release`,
  /** Hand it back to automation — `conversations.return_to_ai`. */
  returnToAi: (id: number) =>
    `/admin/qcp/agent/conversations/${enc(String(id))}/return-to-ai`,
  /** The single send. Free-form or template, discriminated by `kind`. */
  reply: (id: number) => `/admin/qcp/agent/conversations/${enc(String(id))}/reply`,
  /** Ask for a draft. Returns text; it has no path to a send. */
  suggest: (id: number) => `/admin/qcp/agent/conversations/${enc(String(id))}/suggest`,
} as const;

/* ----------------------------------------------------------------- types */

/** Who actually produced a message. The backend derives it from the audit log. */
export type Speaker = "customer" | "ai" | "agent" | "automation";

export type AgentAiState = {
  /** Is the AI answering customers at all? Ships false. */
  enabled?: boolean;
  /** The same switch, read as "AI replies are stopped". Ships true. */
  kill_switch?: boolean;
  /** Is there a model to call — i.e. a key? Distinct from the switch. */
  configured?: boolean;
  /** May an agent ask for a draft? A separate switch, also ships false. */
  suggestions_enabled?: boolean;
  model?: string | null;
  prompt_version?: string | null;
  /**
   * A third state, and not a rename of `enabled` or `kill_switch`: the switch
   * is on and no reply can route anywhere, so the AI answers nobody. An AI
   * reply is a send, a send needs an `ai_support_reply` engagement routing
   * rule, and a missing rule is refused deep inside the gateway where the
   * operator who just flipped the switch will never look.
   */
  misconfigured?: boolean;
  /** `AI_BLOCKED_SWITCH_OFF` | `AI_BLOCKED_NO_PRODUCT` | `AI_BLOCKED_NO_ROUTE`. */
  blocker?: string | null;
  /**
   * Which product, and which languages. Cameroon is francophone and
   * anglophone and the router matches on locale, so a rule created for `en`
   * alone answers anglophone customers and silently strands every French
   * speaker — which is why the locales are named rather than counted.
   */
  gaps?: { product: string; locales: string[] }[];
};

export type AgentQueueItem = {
  conversation_id: number;
  phone_e164: string;
  display_name?: string | null;
  state?: string;
  product?: string | null;
  account?: string | null;
  account_purpose?: string | null;
  unread_count?: number;
  locale?: string | null;
  last_inbound_at?: string | null;
  /** Seconds since this customer started waiting to be answered. */
  waiting_seconds?: number;
  service_window_open?: boolean;
  service_window_expires_at?: string | null;
  /** Ownership, without an id: mine, or somebody's name. */
  mine?: boolean;
  held_by?: string | null;
  /** False for a Verify thread or one no product owns; the reason says which. */
  answerable?: boolean;
  answerable_reason?: string | null;
  /** Automation stopped and asked for a person. */
  escalated?: boolean;
  handover_reason?: string | null;
  waiting_since?: string | null;
  /** Escalated, unclaimed, and past the backend's overdue threshold. */
  overdue?: boolean;
};

export type AgentQueue = {
  items?: AgentQueueItem[];
  total?: number;
  ai?: AgentAiState;
};

export type AgentMessage = {
  id: number;
  message_uid?: string;
  direction: "inbound" | "outbound";
  kind?: string;
  status?: string;
  intent?: string | null;
  product?: string | null;
  body?: string | null;
  /** customer | ai | agent | automation — derived server-side, not guessed. */
  author?: string | null;
  /** A name for a human, the model for the AI, the product slug otherwise. */
  author_label?: string | null;
  suppressed_reason?: string | null;
  error_code?: string | null;
  created_at?: string | null;
};

/** The `/suggest` response. `draft` is null whenever the AI declined. */
export type AgentSuggestion = {
  conversation_id?: number;
  draft?: string | null;
  escalate?: boolean;
  reason?: string | null;
  model?: string | null;
  prompt_version?: string | null;
  service_window_open?: boolean;
  /** Pinned false in the contract: this endpoint has no send path. */
  auto_sent?: false;
  notice?: string;
};

export type AgentTemplate = {
  /** What the reply endpoint takes. A template is addressed by intent. */
  intent: string;
  name: string;
  language?: string | null;
  category?: string | null;
  body?: string | null;
  variables?: string[] | null;
};

export type AgentThread = {
  conversation?: AgentQueueItem | null;
  messages?: AgentMessage[];
  next_before_id?: number | null;
  ai?: AgentAiState;
  templates?: AgentTemplate[];
};

/** The reply payload. `kind` is the discriminator the backend switches on. */
export type ReplyPayload =
  | {
      kind: "text";
      body: string;
      client_token: string;
      /** Audit only: did the human send the AI's words, and did they edit them? */
      from_suggestion: boolean;
      suggestion_edited: boolean;
    }
  | {
      kind: "template";
      intent: string;
      variables: string[];
      client_token: string;
    };

/**
 * A fresh idempotency handle per composed message.
 *
 * Without one the gateway derives a key that buckets by five minutes, and a
 * free-form send carries no template or variables to tell two apart — so an
 * agent's second sentence inside that window would come back `duplicate` and
 * never reach the customer. Re-sending the *same* token is what makes a
 * double-clicked button harmless, which is why it is minted once per payload
 * and not once per request.
 */
export function clientToken(): string {
  const rand = Math.random().toString(36).slice(2);
  return `console-${Date.now().toString(36)}-${rand}`.slice(0, 60);
}

/* ------------------------------------------------------------ predicates */

/**
 * The Verify lock.
 *
 * Quata Verify carries authentication and nothing else. This console offers no
 * way to put a message on it — no AI draft, no free-form box, no template
 * picker — because everything it could legitimately send there is a security
 * code, and a security code is never composed by a person on a support screen.
 *
 * Returns a sentence rather than a boolean so the screen has something to
 * *say*. A disabled control with no explanation is how an agent decides the
 * tool is broken.
 */
export function verifyNumberLock(
  conversation: { account_purpose?: string | null } | null | undefined
): string | null {
  if (!conversation) return null;
  if (conversation.account_purpose !== "authentication") return null;
  return (
    "This thread is on Quata Verify, the number that carries security codes for " +
    "every QUATA product. Nothing may be sent from here — not a typed reply, not " +
    "a template, and the AI does not draft for it at all. If this customer needs " +
    "support, answer them on the QUATA number instead."
  );
}

/**
 * The AI's draft, or nothing.
 *
 * Called before the draft is rendered *or* loaded into the composer, so a
 * suggestion that should never have been generated cannot reach the screen
 * even if the backend produced one. The screen has no other route to a draft.
 */
export function visibleSuggestion(
  conversation: { account_purpose?: string | null } | null | undefined,
  suggestion: AgentSuggestion | null | undefined,
  ai: AgentAiState | undefined
): AgentSuggestion | null {
  if (!suggestion) return null;
  // Never on Verify. Not for any reason, not in any state.
  if (verifyNumberLock(conversation)) return null;
  // Drafting has its own switch. Off means no draft reaches this screen, and
  // a draft sitting in a composer is one keystroke from being a sent message.
  if (ai && ai.suggestions_enabled === false) return null;
  return suggestion;
}

export type ReplyBlocker = {
  code: string;
  title: string;
  detail: string;
  /** True when a template can still go out — i.e. only free-form is barred. */
  templateStillAllowed: boolean;
};

/**
 * Everything standing between this agent and a sent message, worst first.
 *
 * The page renders the first one and disables the composer on it. Each carries
 * the reason, because every one of these is a rule an agent will otherwise
 * read as a bug.
 */
export function replyBlockers(
  conversation: AgentQueueItem | null | undefined
): ReplyBlocker[] {
  const out: ReplyBlocker[] = [];
  if (!conversation) return out;

  const lock = verifyNumberLock(conversation);
  if (lock) {
    out.push({
      code: "verify_number",
      title: "Nothing can be sent on Quata Verify",
      detail: lock,
      templateStillAllowed: false,
    });
    // Everything else is moot once this holds.
    return out;
  }

  if (conversation.answerable === false) {
    out.push({
      code: conversation.answerable_reason || "not_answerable",
      title: "This thread cannot be answered from here",
      detail:
        "No product owns this conversation, so there is nobody to send it as. " +
        "An inbound that two products could both claim is given to neither — " +
        "attribute it on the conversations screen first.",
      templateStillAllowed: false,
    });
    return out;
  }

  if (!conversation.mine) {
    out.push(
      conversation.held_by
        ? {
            code: "claimed_by_other",
            title: "Someone else is on this thread",
            detail:
              `It is assigned to ${conversation.held_by}. They have to release it ` +
              "before you can reply, so the customer never gets two different answers.",
            templateStillAllowed: false,
          }
        : {
            code: "unclaimed",
            title: "Claim this conversation first",
            detail:
              "Nobody is on this thread yet. Claiming it puts your name on it so two " +
              "agents don't answer the same customer twice.",
            templateStillAllowed: false,
          }
    );
  }

  if (conversation.service_window_open === false) {
    out.push({
      code: "window_closed",
      title: "The 24-hour window has closed",
      detail:
        "WhatsApp only allows a free-form reply within 24 hours of the customer's " +
        "last message. That deadline has passed, so Meta will reject anything you " +
        "type — this is their rule, not a fault here. An approved template can " +
        "still go out, and it reopens the window as soon as they reply.",
      templateStillAllowed: true,
    });
  }

  return out;
}

/**
 * Can a template go out?
 *
 * Blocked by everything a free-form reply is blocked by *except* the closed
 * window — an approved template is precisely the thing Meta still carries once
 * the 24 hours are up.
 */
export function canSendTemplate(
  conversation: AgentQueueItem | null | undefined
): boolean {
  const blockers = replyBlockers(conversation);
  return blockers.length > 0 && blockers.every((b) => b.templateStillAllowed);
}

/** May this agent ask the AI for a draft on this thread? */
export function canAskForDraft(
  conversation: AgentQueueItem | null | undefined,
  ai: AgentAiState | undefined
): boolean {
  if (!conversation) return false;
  if (verifyNumberLock(conversation)) return false;
  if (!conversation.mine) return false;
  if (conversation.service_window_open === false) return false;
  return ai?.suggestions_enabled !== false;
}

/**
 * Who said it.
 *
 * The backend derives authorship from the audit log — `ai.*` actions mark the
 * bot, `agent.*` with an actor marks a human — so the console renders that
 * answer rather than inventing its own. An outbound row it could not attribute
 * arrives as `automation` and is shown as such: guessing an author on a thread
 * that carries money talk is not a small mistake.
 */
export function speakerOf(m: AgentMessage): Speaker {
  if (m.direction === "inbound") return "customer";
  const author = (m.author ?? "").toLowerCase();
  if (author === "ai") return "ai";
  if (author === "agent") return "agent";
  if (author === "customer") return "customer";
  return "automation";
}

/** The name to print above a bubble. */
export function speakerName(m: AgentMessage, customerLabel: string): string {
  switch (speakerOf(m)) {
    case "customer":
      return m.author_label || customerLabel;
    case "ai":
      return m.author_label ? `Quata AI · ${m.author_label}` : "Quata AI";
    case "agent":
      return m.author_label || "Agent";
    default:
      return m.author_label ? `Automated · ${m.author_label}` : "Automated";
  }
}

/* -------------------------------------------------------------- wait time */

/**
 * Minutes this customer has been waiting.
 *
 * Computed from the absolute instant the wait started — the escalation clock
 * when the AI handed the thread over, and the customer's last message
 * otherwise — rather than from the server's `waiting_seconds`, so a wait keeps
 * climbing on screen between polls instead of freezing at whatever it was when
 * the page last fetched. `waiting_seconds` is the fallback for a row that
 * carries neither timestamp.
 */
export function waitMinutes(item: AgentQueueItem, now: number): number | null {
  const raw = item.waiting_since ?? item.last_inbound_at ?? null;
  if (raw) {
    const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(raw);
    const t = new Date(hasZone ? raw : `${raw}Z`).getTime();
    if (!Number.isNaN(t)) return Math.max(0, Math.floor((now - t) / 60000));
  }
  if (typeof item.waiting_seconds === "number") {
    return Math.max(0, Math.floor(item.waiting_seconds / 60));
  }
  return null;
}

/** `42m`, `3h 05m`, `2d`. Short enough to set large. */
export function formatWait(mins: number | null): string {
  if (mins == null) return "—";
  if (mins < 60) return `${mins}m`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ${String(mins % 60).padStart(2, "0")}m`;
  return `${Math.floor(hrs / 24)}d ${hrs % 24}h`;
}

export type WaitTone = "calm" | "warn" | "urgent";

/**
 * How loud the wait should be.
 *
 * The brief for this screen is that forty minutes must be obvious across the
 * room, so the thresholds are deliberately low and the top one is red.
 */
export function waitTone(mins: number | null): WaitTone {
  if (mins == null) return "calm";
  if (mins >= 15) return "urgent";
  if (mins >= 5) return "warn";
  return "calm";
}

/**
 * One queue out of the two the backend serves.
 *
 * "Waiting" is unassigned; "mine" is what this agent already holds. Merging
 * them is what stops a thread vanishing from the screen the moment it is
 * claimed — an agent who claims a conversation and watches it disappear will
 * claim it again. Deduped by id, oldest wait first.
 */
export function mergeQueues(
  waiting: AgentQueueItem[],
  mine: AgentQueueItem[],
  now: number
): AgentQueueItem[] {
  const byId = new Map<number, AgentQueueItem>();
  for (const item of [...waiting, ...mine]) byId.set(item.conversation_id, item);
  return [...byId.values()].sort((a, b) => {
    const wa = waitMinutes(a, now);
    const wb = waitMinutes(b, now);
    if (wa == null && wb == null) return a.conversation_id - b.conversation_id;
    if (wa == null) return 1;
    if (wb == null) return -1;
    if (wa !== wb) return wb - wa;
    return a.conversation_id - b.conversation_id;
  });
}

/**
 * The categories the AI is required to hand over rather than answer.
 *
 * Rendered as a badge so the agent knows before they open the thread that it
 * is about money, KYC, fraud, a complaint, a legal threat or someone
 * distressed — these are the threads where a wrong answer is expensive. The
 * keys are the backend's own reason strings (`handover.R_*`, and the
 * classifier's intent names).
 */
export const HANDOVER_LABELS: Record<string, string> = {
  money: "Money",
  kyc: "KYC",
  fraud: "Fraud",
  complaint: "Complaint",
  legal: "Legal",
  distress: "Distressed",
  account_status: "Account",
  auth: "Security code",
  injection: "Suspicious",
  sensitive_topic: "Sensitive",
  human_requested: "Asked for a person",
  low_confidence: "Unclear",
  repeated_question: "Asked before",
  unsupported_language: "Language",
  unattributed: "Unattributed",
  ai_disabled: "AI off",
  provider_error: "AI failed",
  unparseable: "Unclear",
  classifier_unsafe: "Unsafe",
  ungrounded_fact: "Unverified figure",
  outside_service_window: "Window closed",
  not_engagement_number: "Verify number",
};

/** A human-readable label for a handover reason, falling back to the raw one. */
export function handoverLabel(reason: string | null | undefined): string | null {
  if (!reason) return null;
  return HANDOVER_LABELS[reason] ?? reason.replace(/_/g, " ");
}
