import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * The QCP agent console, driven in a browser against a fake AI-support backend.
 *
 * This screen is the one place in QCP where a human, an AI and a customer all
 * write into the same thread — on a platform that carries money, KYC and, on
 * the other number, every login code in the fleet. The tests below are
 * therefore not about layout. They are about the things that must hold before
 * this screen is allowed near a real customer:
 *
 *  1. **Nothing can be sent on Quata Verify.** No draft is rendered, no
 *     composer exists, and the reason is on screen.
 *  2. **A draft is asked for, and it is a suggestion, not a sent message.**
 *     Nothing calls the AI on load, and nothing reaches the customer until a
 *     human presses Send.
 *  3. **Outside Meta's 24-hour window, free-form is impossible** — and the
 *     agent is told why, in Meta's terms, so they don't conclude the tool is
 *     broken.
 *  4. **The queue is oldest-first with the wait time legible**, because the
 *     forty-minute customer is the whole reason this screen exists — and an
 *     escalation nobody has picked up is called out as overdue.
 *  5. **An empty queue reads as correct**, because QCP is dormant and empty is
 *     the state the first real agent will meet.
 *
 * The fake serves the *real* contract — `routes_admin_agent.py` and
 * `schemas/whatsapp_agent.py` — including its central decision that **no
 * response carries a staff id**: ownership arrives as `mine` and a display
 * name, never a `users.id` the console could compare or leak.
 *
 * Faked inline rather than through `qcp-world.ts`: these routes are new, and a
 * fake that lives next to the assertions is easier to keep honest than one
 * shared with five other specs.
 */

const TOKEN = "e2e-agent-token";
const ME_ID = 7;

const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-headers": "*",
  "access-control-allow-methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
};

/** A draft that must never appear on a Verify thread — a needle to grep the DOM for. */
const VERIFY_DRAFT = "FORBIDDEN-DRAFT-ON-VERIFY-should-never-render";

const DRAFT = "Your order is on its way and should arrive shortly.";

type Recorded = { method: string; path: string; body: Record<string, unknown> | null };

type Ai = Record<string, unknown>;

type World = {
  waiting: Record<string, unknown>;
  mine: Record<string, unknown>;
  threads: Record<number, Record<string, unknown>>;
  suggestion: Record<string, unknown>;
  requests: Recorded[];
  /** `"GET /admin/qcp/agent/queue/unassigned"` → forced response. */
  forced: Map<string, { status: number; body: unknown }>;
};

function minutesAgo(mins: number): string {
  return new Date(Date.now() - mins * 60_000).toISOString();
}

const AI_ON: Ai = {
  enabled: true,
  kill_switch: false,
  configured: true,
  suggestions_enabled: true,
  model: "test-model",
  prompt_version: "v1",
};

/** One queue row / conversation, in the shape `AgentQueueItemOut` really has. */
function conversation(over: Record<string, unknown> = {}) {
  return {
    conversation_id: 1,
    phone_e164: "+237650000001",
    display_name: "Ngwa Peter",
    state: "open",
    product: "quatafood",
    account: "quata",
    account_purpose: "engagement",
    unread_count: 0,
    locale: "en",
    last_inbound_at: minutesAgo(12),
    waiting_seconds: 720,
    service_window_open: true,
    service_window_expires_at: new Date(Date.now() + 60 * 60_000).toISOString(),
    // Ownership without an id — the backend never sends one.
    mine: true,
    held_by: null,
    answerable: true,
    answerable_reason: null,
    escalated: false,
    handover_reason: null,
    waiting_since: null,
    overdue: false,
    ...over,
  };
}

function emptyWorld(): World {
  return {
    waiting: { items: [], total: 0, ai: { ...AI_ON } },
    mine: { items: [], total: 0, ai: { ...AI_ON } },
    threads: {},
    suggestion: {
      conversation_id: 1,
      draft: DRAFT,
      escalate: false,
      reason: "safe_intent_answered_from_facts",
      model: "test-model",
      prompt_version: "v1",
      service_window_open: true,
      auto_sent: false,
    },
    requests: [],
    forced: new Map(),
  };
}

/** One engagement thread, claimed by me, with a draft available on request. */
function draftWorld(): World {
  const w = emptyWorld();
  const c = conversation();
  w.mine = { items: [c], total: 1, ai: { ...AI_ON } };
  w.threads[1] = {
    conversation: c,
    messages: [
      {
        id: 10,
        message_uid: "m10",
        direction: "inbound",
        kind: "text",
        status: "delivered",
        body: "Where is my order?",
        author: "customer",
        author_label: "Ngwa Peter",
        created_at: minutesAgo(14),
      },
      {
        id: 11,
        message_uid: "m11",
        direction: "outbound",
        kind: "text",
        status: "delivered",
        body: "Let me check that for you.",
        author: "ai",
        author_label: "test-model",
        created_at: minutesAgo(13),
      },
      {
        id: 12,
        message_uid: "m12",
        direction: "outbound",
        kind: "text",
        status: "delivered",
        body: "Hello, I am taking over from here.",
        author: "agent",
        author_label: "Bernadette N.",
        created_at: minutesAgo(9),
      },
    ],
    next_before_id: null,
    ai: { ...AI_ON },
    templates: [],
  };
  return w;
}

async function useWorld(page: Page, world: World): Promise<World> {
  await page.addInitScript((token) => {
    window.localStorage.setItem("quata_token", token);
  }, TOKEN);

  await page.route("**/api/v1/**", async (route: Route) => {
    const req = route.request();
    const url = new URL(req.url());
    const path = url.pathname.replace(/^\/api\/v1/, "");
    const method = req.method();

    let body: Record<string, unknown> | null = null;
    try {
      body = (req.postDataJSON() as Record<string, unknown>) ?? null;
    } catch {
      body = null;
    }
    if (path.startsWith("/admin/qcp")) world.requests.push({ method, path, body });

    const reply = handle(world, method, path);
    await route.fulfill({
      status: reply.status,
      contentType: "application/json",
      headers: CORS,
      body: JSON.stringify(reply.body),
    });
  });

  return world;
}

function handle(
  w: World,
  method: string,
  path: string
): { status: number; body: unknown } {
  const forced = w.forced.get(`${method} ${path}`);
  if (forced) return forced;

  if (path === "/auth/me") {
    return {
      status: 200,
      body: {
        id: ME_ID,
        email: "agent@quatadigital.com",
        full_name: "Bernadette N.",
        // Deliberately NOT a super admin: a support agent in Bamenda holds
        // `whatsapp:agent` and nothing else, and must still get in.
        role: "support",
        department: null,
        phone: null,
        job_title: null,
        avatar_url: null,
        permissions: ["whatsapp:agent"],
        requires_2fa: false,
        has_2fa: true,
        must_reset_password: false,
      },
    };
  }

  if (path === "/admin/qcp/agent/queue/unassigned") return { status: 200, body: w.waiting };
  if (path === "/admin/qcp/agent/queue") return { status: 200, body: w.mine };

  const threadMatch = /^\/admin\/qcp\/agent\/conversations\/(\d+)\/thread$/.exec(path);
  if (threadMatch && method === "GET") {
    const t = w.threads[Number(threadMatch[1])];
    return t
      ? { status: 200, body: t }
      : { status: 404, body: { detail: "Conversation not found" } };
  }

  if (/\/suggest$/.test(path) && method === "POST") {
    return { status: 200, body: w.suggestion };
  }

  const actionMatch = /^\/admin\/qcp\/agent\/conversations\/(\d+)\/([a-z-]+)$/.exec(path);
  if (actionMatch && method === "POST") {
    return {
      status: 200,
      body: { conversation_id: Number(actionMatch[1]), state: "open", mine: true },
    };
  }

  return { status: 200, body: { items: [], total: 0, page: 1, page_size: 25 } };
}

function postsTo(w: World, path: string): Recorded[] {
  return w.requests.filter((r) => r.method === "POST" && r.path === path);
}

/** Fails the test on an uncaught exception rather than letting it pass quietly. */
function watchForCrashes(page: Page): string[] {
  const crashes: string[] = [];
  page.on("pageerror", (err) => crashes.push(String(err)));
  return crashes;
}

const queueRows = (page: Page) => page.getByTestId("queue-row");
const composer = (page: Page) => page.getByTestId("reply-body");
const sendButton = (page: Page) => page.getByRole("button", { name: /send reply/i });
const draftButton = (page: Page) => page.getByTestId("ask-for-draft");

/* --------------------------------------------------------------- the tests */

test.describe("QCP agent console", () => {
  test("an empty queue reads as correct, not broken", async ({ page }) => {
    const crashes = watchForCrashes(page);
    await useWorld(page, emptyWorld());
    await page.goto("/admin/qcp/agent");

    await expect(
      page.getByRole("heading", { name: /agent console/i }).first()
    ).toBeVisible();
    await expect(page.getByText(/nobody is waiting/i)).toBeVisible();
    // The dormancy has to be named, or somebody "fixes" a working system.
    await expect(page.getByText(/dormant/i).first()).toBeVisible();
    await expect(page.getByText(/couldn't load/i)).toHaveCount(0);
    expect(crashes).toEqual([]);
  });

  test("the queue is oldest-first and the wait time is legible", async ({ page }) => {
    const w = emptyWorld();
    w.waiting = {
      items: [
        conversation({ conversation_id: 2, display_name: "Recent", last_inbound_at: minutesAgo(3), mine: false }),
        conversation({ conversation_id: 3, display_name: "Longest", last_inbound_at: minutesAgo(42), mine: false }),
        conversation({ conversation_id: 4, display_name: "Middle", last_inbound_at: minutesAgo(12), mine: false }),
      ],
      total: 3,
      ai: { ...AI_ON },
    };
    await useWorld(page, w);
    await page.goto("/admin/qcp/agent");

    await expect(queueRows(page)).toHaveCount(3);
    await expect(queueRows(page).first()).toContainText("Longest");
    await expect(queueRows(page).first().getByTestId("wait")).toHaveText("42m");
    // Forty minutes has to be loud, not another grey line of text.
    await expect(queueRows(page).first().getByTestId("wait")).toHaveAttribute(
      "data-tone",
      "urgent"
    );
    await expect(queueRows(page).nth(2)).toContainText("Recent");
  });

  test("an escalation nobody has picked up is called out, not just listed", async ({
    page,
  }) => {
    const w = emptyWorld();
    w.waiting = {
      items: [
        conversation({
          conversation_id: 5,
          display_name: "Waiting on a person",
          mine: false,
          escalated: true,
          overdue: true,
          handover_reason: "sensitive_topic",
          waiting_since: minutesAgo(38),
        }),
      ],
      total: 1,
      ai: { ...AI_ON },
    };
    await useWorld(page, w);
    await page.goto("/admin/qcp/agent");

    await expect(page.getByTestId("overdue-banner")).toBeVisible();
    await expect(queueRows(page).first()).toContainText(/nobody has picked this up/i);
    // The category the AI refused to answer is on the row, before it is opened.
    await expect(queueRows(page).first()).toContainText(/sensitive/i);
  });

  test("the thread tells customer, AI and named human apart", async ({ page }) => {
    await useWorld(page, draftWorld());
    await page.goto("/admin/qcp/agent");
    await queueRows(page).first().click();

    await expect(page.getByTestId("bubble")).toHaveCount(3);
    await expect(page.getByTestId("bubble").nth(0)).toHaveAttribute(
      "data-speaker",
      "customer"
    );
    await expect(page.getByTestId("bubble").nth(1)).toHaveAttribute("data-speaker", "ai");
    await expect(page.getByTestId("bubble").nth(1)).toContainText("Quata AI");
    await expect(page.getByTestId("bubble").nth(2)).toHaveAttribute(
      "data-speaker",
      "agent"
    );
    await expect(page.getByTestId("bubble").nth(2)).toContainText("Bernadette N.");
  });

  test("a draft is asked for, marked as a suggestion, and sends nothing on its own", async ({
    page,
  }) => {
    const w = await useWorld(page, draftWorld());
    await page.goto("/admin/qcp/agent");
    await queueRows(page).first().click();

    // Opening a thread must not consult the AI and must not send anything.
    await expect(composer(page)).toHaveValue("");
    expect(postsTo(w, "/admin/qcp/agent/conversations/1/suggest")).toHaveLength(0);
    expect(postsTo(w, "/admin/qcp/agent/conversations/1/reply")).toHaveLength(0);

    await draftButton(page).click();
    await expect(composer(page)).toHaveValue(DRAFT);
    // It must be obvious this is a proposal.
    await expect(page.getByText(/suggested draft/i).first()).toBeVisible();
    await expect(page.getByText(/nothing is sent until you press send/i)).toBeVisible();
    // …and asking for one still sends nothing to the customer.
    expect(postsTo(w, "/admin/qcp/agent/conversations/1/reply")).toHaveLength(0);

    await composer(page).fill("Your order is out for delivery now.");
    await sendButton(page).click();

    await expect
      .poll(() => postsTo(w, "/admin/qcp/agent/conversations/1/reply").length)
      .toBe(1);
    const sent = postsTo(w, "/admin/qcp/agent/conversations/1/reply")[0];
    expect(sent.body).toMatchObject({
      kind: "text",
      body: "Your order is out for delivery now.",
      from_suggestion: true,
      suggestion_edited: true,
    });
    // The idempotency handle the gateway needs to tell two sentences apart.
    expect(String((sent.body ?? {}).client_token ?? "")).not.toEqual("");
  });

  test("a draft the AI refused carries no body into the box", async ({ page }) => {
    const w = draftWorld();
    w.suggestion = {
      conversation_id: 1,
      draft: null,
      escalate: true,
      reason: "money",
      model: "test-model",
      prompt_version: "v1",
      auto_sent: false,
    };
    await useWorld(page, w);
    await page.goto("/admin/qcp/agent");
    await queueRows(page).first().click();
    await draftButton(page).click();

    await expect(page.getByTestId("suggestion-escalated")).toBeVisible();
    await expect(page.getByText(/did not draft a reply/i)).toBeVisible();
    // The composer stays the agent's own, empty and enabled.
    await expect(composer(page)).toHaveValue("");
    await expect(composer(page)).toBeEnabled();
  });

  test("outside the 24-hour window free-form is impossible and the reason is on screen", async ({
    page,
  }) => {
    const w = draftWorld();
    const closed = conversation({
      service_window_open: false,
      service_window_expires_at: minutesAgo(200),
    });
    w.mine = { items: [closed], total: 1, ai: { ...AI_ON } };
    w.threads[1] = {
      ...w.threads[1],
      conversation: closed,
      templates: [
        {
          intent: "order_update",
          name: "order_update_v2",
          language: "en",
          category: "utility",
          variables: [],
        },
      ],
    };
    await useWorld(page, w);
    await page.goto("/admin/qcp/agent");
    await queueRows(page).first().click();

    await expect(composer(page)).toBeDisabled();
    await expect(page.getByText(/24 hours/i).first()).toBeVisible();
    await expect(page.getByText(/their rule, not a fault here/i)).toBeVisible();
    // A template is the only way out, so it has to be offered right there.
    await expect(page.getByTestId("template-picker")).toBeVisible();
    // And the AI is not asked to draft prose that could not be sent anyway.
    await expect(draftButton(page)).toHaveCount(0);
  });

  test("a Verify thread offers no composer and never renders a draft", async ({ page }) => {
    const w = draftWorld();
    const verify = conversation({
      account: "quata-verify",
      account_purpose: "authentication",
      product: "quatapay",
      answerable: false,
      answerable_reason: "verify_number_not_agent_answerable",
    });
    w.mine = { items: [verify], total: 1, ai: { ...AI_ON } };
    // The backend should never produce this draft. If it ever did, the screen
    // still must not put it in front of an agent.
    w.suggestion = { conversation_id: 1, draft: VERIFY_DRAFT, escalate: false };
    w.threads[1] = {
      conversation: verify,
      messages: [
        {
          id: 20,
          message_uid: "m20",
          direction: "inbound",
          kind: "text",
          status: "delivered",
          body: "I did not get my code",
          author: "customer",
          created_at: minutesAgo(5),
        },
      ],
      ai: { ...AI_ON },
      templates: [
        {
          intent: "login_otp",
          name: "otp_code",
          language: "en",
          category: "authentication",
          variables: ["1"],
        },
      ],
    };
    await useWorld(page, w);
    await page.goto("/admin/qcp/agent");
    await queueRows(page).first().click();

    await expect(page.getByText(/quata verify/i).first()).toBeVisible();
    await expect(composer(page)).toHaveCount(0);
    await expect(sendButton(page)).toHaveCount(0);
    await expect(draftButton(page)).toHaveCount(0);
    await expect(page.getByTestId("template-picker")).toHaveCount(0);
    expect(await page.content()).not.toContain(VERIFY_DRAFT);
    // Nothing was even asked of the AI about this thread.
    expect(postsTo(w, "/admin/qcp/agent/conversations/1/suggest")).toHaveLength(0);
  });

  test("the kill switch is stated and human replies keep working", async ({ page }) => {
    const w = draftWorld();
    const off: Ai = { ...AI_ON, enabled: false, kill_switch: true, suggestions_enabled: false };
    w.mine = { ...w.mine, ai: off };
    w.threads[1] = { ...w.threads[1], ai: off };
    await useWorld(page, w);
    await page.goto("/admin/qcp/agent");
    await queueRows(page).first().click();

    await expect(page.getByText(/ai replies are switched off/i).first()).toBeVisible();
    // Drafting is gone…
    await expect(draftButton(page)).toHaveCount(0);
    // …and the human is entirely unaffected, which is the point of the switch.
    await expect(composer(page)).toBeEnabled();
    await expect(composer(page)).toHaveValue("");
    expect(await page.content()).not.toContain(DRAFT);
  });

  test("claim, release and hand back to AI hit their own routes", async ({ page }) => {
    const w = draftWorld();
    const unclaimed = conversation({ mine: false, held_by: null });
    w.mine = { items: [], total: 0, ai: { ...AI_ON } };
    w.waiting = { items: [unclaimed], total: 1, ai: { ...AI_ON } };
    w.threads[1] = { ...w.threads[1], conversation: unclaimed };
    await useWorld(page, w);
    await page.goto("/admin/qcp/agent");
    await queueRows(page).first().click();

    // Unclaimed means it cannot be replied to yet, and says so.
    await expect(composer(page)).toBeDisabled();
    await expect(page.getByText(/claim this conversation first/i)).toBeVisible();

    await page.getByRole("button", { name: /^claim$/i }).click();
    await expect
      .poll(() => postsTo(w, "/admin/qcp/agent/conversations/1/claim").length)
      .toBe(1);

    // Now owned by me, the release and hand-back actions appear.
    w.threads[1] = { ...w.threads[1], conversation: conversation() };
    await page.getByRole("button", { name: /refresh thread/i }).click();
    await page.getByRole("button", { name: /release/i }).click();
    await expect
      .poll(() => postsTo(w, "/admin/qcp/agent/conversations/1/release").length)
      .toBe(1);

    await page.getByRole("button", { name: /hand back to ai/i }).click();
    await expect
      .poll(() => postsTo(w, "/admin/qcp/agent/conversations/1/return-to-ai").length)
      .toBe(1);
  });

  test("a failed load is an error, not an empty queue", async ({ page }) => {
    const w = emptyWorld();
    w.forced.set("GET /admin/qcp/agent/queue/unassigned", {
      status: 500,
      body: { detail: "boom" },
    });
    await useWorld(page, w);
    await page.goto("/admin/qcp/agent");

    await expect(page.getByText(/couldn't load/i)).toBeVisible();
    await expect(page.getByText(/nobody is waiting/i)).toHaveCount(0);
  });
});
