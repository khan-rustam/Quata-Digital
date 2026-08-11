import { expect, test, type Page } from "@playwright/test";
import {
  FAKE,
  FAKE_VALUES,
  barrenWorld,
  freshWorld,
  product,
  requestsTo,
  useWorld,
  type World,
} from "./qcp-world";

/**
 * The QCP admin write screens, driven in a browser.
 *
 * Everything else that guards this console is static: typecheck, lint, and the
 * source-level secret invariants in `qcp-secret-invariants.spec.ts`. None of
 * them has ever *saved a credential*, minted a key, or switched a number on.
 * Until this file existed, the first execution of those code paths would have
 * been a human operator, in production, on Quata Verify — the number every
 * login code in the fleet goes out from, and the one whose restriction locks
 * QuataFood users out of accounts that have no email fallback.
 *
 * So these tests are deliberately about the dangerous half:
 *
 *  1. a credential survives a save and is never rendered back, and a blank box
 *     means "keep what is stored" rather than "clear it";
 *  2. a number cannot be switched on while it is unconfigured, and switching
 *     one on costs a typed slug and a justification;
 *  3. a minted key appears exactly once and cannot be recovered;
 *  4. an illegal category/number pairing is refused with a sentence an
 *     operator can act on;
 *  5. every screen is legible when nothing is configured — the state the first
 *     real operator meets, and the one where "this looks broken" gets someone
 *     to fix a working system.
 *
 * The backend is a fake (`qcp-world.ts`); the screens, the components, the
 * fetch layer and the refusal rendering are all real.
 */

/** Fails the test on an uncaught exception rather than letting it pass quietly. */
function watchForCrashes(page: Page): string[] {
  const crashes: string[] = [];
  page.on("pageerror", (err) => crashes.push(String(err)));
  return crashes;
}

const dialogOf = (page: Page) => page.getByRole("dialog");

/** An account card on the overview: the only `p-5 ring-soft` block there. */
const accountCard = (page: Page, name: string) =>
  page.locator("div.ring-soft.p-5").filter({ hasText: name });

/** A credential/presence field, scoped by the input it wraps. */
const fieldOf = (page: Page, id: string) =>
  dialogOf(page).locator(`div.grid.gap-2:has(> input#${id})`);

const CRED_IDS = [
  "phone_number_id",
  "waba_id",
  "access_token",
  "app_secret",
  "webhook_verify_token",
] as const;

const CRED_VALUES: Record<(typeof CRED_IDS)[number], string> = {
  phone_number_id: FAKE.phoneNumberId,
  waba_id: FAKE.wabaId,
  access_token: FAKE.accessToken,
  app_secret: FAKE.appSecret,
  webhook_verify_token: FAKE.verifyToken,
};

/** Nothing the operator typed may be anywhere in the document, ever. */
async function expectNoSecretsOnScreen(page: Page) {
  const html = await page.content();
  for (const value of FAKE_VALUES) {
    expect(
      html.includes(value),
      `a stored credential was rendered into the page`
    ).toBe(false);
  }
}

/* ========================================================================= */
/* 1. Credentials                                                            */
/* ========================================================================= */

test.describe("QCP console — credentials", () => {
  test("a saved credential is stored, never rendered back, and a blank box keeps it", async ({
    page,
  }) => {
    const crashes = watchForCrashes(page);
    const world = await useWorld(page, freshWorld());

    await page.goto("/admin/qcp");
    await expect(page.getByText("QCP is dormant")).toBeVisible();

    const verify = accountCard(page, "Quata Verify");
    await verify.getByRole("button", { name: /configure credentials/i }).click();

    const dialog = dialogOf(page);
    await expect(dialog.getByText("Configure Quata Verify")).toBeVisible();

    // Nothing is configured yet, and every box is empty because there is
    // nothing to prefill — the API returns booleans, not values.
    for (const id of CRED_IDS) {
      await expect(fieldOf(page, id).getByText("Not configured")).toBeVisible();
      await expect(dialog.locator(`#${id}`)).toHaveValue("");
    }

    for (const id of CRED_IDS) {
      await dialog.locator(`#${id}`).fill(CRED_VALUES[id]);
    }
    await dialog.getByRole("button", { name: "Save credentials" }).click();
    await expect(dialog).toBeHidden();

    const puts = requestsTo(world, "PUT", "/admin/qcp/accounts/quata-verify/credentials");
    expect(puts).toHaveLength(1);
    expect(puts[0].body).toEqual({
      phone_number_id: FAKE.phoneNumberId,
      waba_id: FAKE.wabaId,
      access_token: FAKE.accessToken,
      app_secret: FAKE.appSecret,
      webhook_verify_token: FAKE.verifyToken,
    });
    expect(world.account("quata-verify")!.secrets.access_token).toBe(FAKE.accessToken);

    // The confirmation names a digest, not a value.
    const toast = page.getByRole("status").first();
    await expect(toast).toContainText("Replaced 5 values");
    await expectNoSecretsOnScreen(page);

    // --- reload: the stored values must not come back ---
    await page.reload();
    await expect(page.getByText("QCP is dormant")).toBeVisible();
    await expect(verify.getByText("Access token")).toBeVisible();
    await expectNoSecretsOnScreen(page);

    await verify.getByRole("button", { name: /configure credentials/i }).click();
    for (const id of CRED_IDS) {
      await expect(fieldOf(page, id).getByText("Configured", { exact: true })).toBeVisible();
      // Still empty. "Configured" is a state, not a value.
      await expect(dialog.locator(`#${id}`)).toHaveValue("");
      await expect(dialog.locator(`#${id}`)).toHaveAttribute(
        "placeholder",
        "Leave blank to keep the stored value"
      );
    }
    await expectNoSecretsOnScreen(page);

    // --- a blank box means "keep", not "clear" ---
    await dialog.locator("#display_phone").fill("+237 6 77 00 00 00");
    await dialog.getByRole("button", { name: "Save credentials" }).click();
    await expect(dialog).toBeHidden();

    const puts2 = requestsTo(world, "PUT", "/admin/qcp/accounts/quata-verify/credentials");
    expect(puts2).toHaveLength(2);
    expect(Object.keys(puts2[1].body ?? {})).toEqual(["display_phone"]);
    expect(world.account("quata-verify")!.secrets.access_token).toBe(FAKE.accessToken);
    expect(world.account("quata-verify")!.secrets.app_secret).toBe(FAKE.appSecret);

    expect(crashes).toEqual([]);
  });

  test("saving an untouched form is refused rather than sent as a clear", async ({ page }) => {
    const world = await useWorld(
      page,
      freshWorld({
        accounts: [
          {
            id: 1,
            slug: "quata-verify",
            name: "Quata Verify",
            purpose: "authentication",
            display_phone: "+237 6 77 00 00 00",
            api_version: "v21.0",
            is_active: false,
            health: "unknown",
            quality_rating: null,
            messaging_limit: null,
            last_checked_at: null,
            last_error: null,
            secrets: {
              phone_number_id: FAKE.phoneNumberId,
              waba_id: FAKE.wabaId,
              access_token: FAKE.accessToken,
            },
          },
        ],
      })
    );

    await page.goto("/admin/qcp");
    await accountCard(page, "Quata Verify")
      .getByRole("button", { name: /configure credentials/i })
      .click();

    const dialog = dialogOf(page);
    await dialog.getByRole("button", { name: "Save credentials" }).click();

    await expect(dialog.getByRole("alert")).toContainText("Nothing to save");
    await expect(dialog.getByRole("alert")).toContainText("keep what is stored");
    expect(requestsTo(world, "PUT", "/admin/qcp/accounts/quata-verify/credentials")).toHaveLength(0);
    expect(world.account("quata-verify")!.secrets.access_token).toBe(FAKE.accessToken);
  });
});

/* ========================================================================= */
/* 2. Switching a number on                                                  */
/* ========================================================================= */

function configuredWorld(): World {
  const w = freshWorld();
  Object.assign(w.account("quata-verify")!, {
    display_phone: "+237 6 77 00 00 00",
    secrets: {
      phone_number_id: FAKE.phoneNumberId,
      waba_id: FAKE.wabaId,
      access_token: FAKE.accessToken,
      app_secret: FAKE.appSecret,
      webhook_verify_token: FAKE.verifyToken,
    },
  });
  return w;
}

test.describe("QCP console — switching a number on", () => {
  test("an unconfigured number cannot be activated at all", async ({ page }) => {
    const world = await useWorld(page, freshWorld());
    await page.goto("/admin/qcp");

    const verify = accountCard(page, "Quata Verify");
    await expect(verify.getByRole("button", { name: /activate this number/i })).toBeDisabled();
    await expect(verify.getByText("Blocked until credentials are set.")).toBeVisible();
    // Testing a number with nothing stored would just be a doomed Graph call.
    await expect(verify.getByRole("button", { name: /test connection/i })).toBeDisabled();

    // The blocker list says what to do about it, in order.
    await expect(page.getByText(/have no usable credentials|has no usable credentials/)).toBeVisible();

    expect(requestsTo(world, "POST", "/admin/qcp/accounts/quata-verify/enable")).toHaveLength(0);
  });

  test("activating costs a typed slug and a justification, and says what it risks", async ({
    page,
  }) => {
    const world = await useWorld(page, configuredWorld());
    await page.goto("/admin/qcp");

    const verify = accountCard(page, "Quata Verify");
    await verify.getByRole("button", { name: /activate this number/i }).click();

    const dialog = dialogOf(page);
    const confirm = dialog.getByRole("button", { name: /^Activate Quata Verify$/ });

    // The consequence is stated at the click, not in a runbook.
    await expect(dialog).toContainText("This number is already in production use by the fleet");
    await expect(dialog).toContainText("second sender");
    await expect(dialog).toContainText("login codes stop arriving across the whole fleet");
    await expect(confirm).toBeDisabled();

    // A justification alone is not enough.
    await dialog.locator("#activation-reason").fill("migrating QuataPay OTP, approved 2026-08-11");
    await expect(confirm).toBeDisabled();

    // Nor is the wrong slug.
    await dialog.locator("#qcp-confirm-phrase").fill("quata");
    await expect(confirm).toBeDisabled();

    // Nor is a justification under the backend's 8-character floor.
    await dialog.locator("#qcp-confirm-phrase").fill("quata-verify");
    await dialog.locator("#activation-reason").fill("why");
    await expect(confirm).toBeDisabled();

    await dialog.locator("#activation-reason").fill("migrating QuataPay OTP, approved 2026-08-11");
    await expect(confirm).toBeEnabled();
    await confirm.click();
    await expect(dialog).toBeHidden();

    const posts = requestsTo(world, "POST", "/admin/qcp/accounts/quata-verify/enable");
    expect(posts).toHaveLength(1);
    expect(posts[0].body).toEqual({
      confirm_slug: "quata-verify",
      justification: "migrating QuataPay OTP, approved 2026-08-11",
    });
    expect(world.account("quata-verify")!.is_active).toBe(true);

    // The screen re-reads rather than assuming: the gate tile flips too.
    await expect(verify.getByText("Active", { exact: true })).toBeVisible();
    await expect(page.getByText("At least one number is switched on")).toBeVisible();
    // Activation alone must not claim QCP is live — two gates are still shut.
    await expect(page.getByText("QCP is dormant")).toBeVisible();
  });

  test("a backend refusal is shown as the backend worded it, and nothing switches on", async ({
    page,
  }) => {
    const world = configuredWorld();
    // The number looks configured to the console but the backend disagrees —
    // a credential cleared in another session, say. The console must relay the
    // backend's own sentence: it names the fields, and "invalid" is not an
    // instruction.
    world.forced.set("POST /admin/qcp/accounts/quata-verify/enable", {
      status: 409,
      body: {
        detail: {
          reason: "not_configured",
          blocking: ["access_token"],
          message:
            "This number is not fully configured. Set access_token before switching it on.",
        },
      },
    });
    await useWorld(page, world);

    await page.goto("/admin/qcp");
    await accountCard(page, "Quata Verify")
      .getByRole("button", { name: /activate this number/i })
      .click();

    const dialog = dialogOf(page);
    await dialog.locator("#activation-reason").fill("migrating QuataPay OTP, approved 2026-08-11");
    await dialog.locator("#qcp-confirm-phrase").fill("quata-verify");
    await dialog.getByRole("button", { name: /^Activate Quata Verify$/ }).click();

    const banner = dialog.getByRole("alert");
    await expect(banner).toBeVisible();
    await expect(banner).toContainText(
      "This number is not fully configured. Set access_token before switching it on."
    );
    await expect(banner).toContainText("Nothing was written.");

    expect(world.account("quata-verify")!.is_active).toBe(false);
    await expect(dialog).toBeVisible();
  });
});

/* ========================================================================= */
/* 3. Minting a product key                                                  */
/* ========================================================================= */

test.describe("QCP console — product keys", () => {
  test("a minted key is shown once and is gone after a reload", async ({ page }) => {
    const world = await useWorld(
      page,
      freshWorld({ products: [product(1, "quatapay", "QuataPay")] })
    );

    await page.goto("/admin/qcp/products");
    const card = page.locator("div.ring-soft.p-5").filter({ hasText: "QuataPay" });
    await expect(card.getByText("Never issued")).toBeVisible();

    await card.getByRole("button", { name: /mint key/i }).click();

    const dialog = dialogOf(page);
    await expect(dialog.getByText("API key for QuataPay")).toBeVisible();

    const plaintext = world.mintedKeys[0];
    expect(plaintext, "the fake backend minted a key").toBeTruthy();
    await expect(dialog.locator("#minted-key")).toHaveText(plaintext);
    await expect(dialog).toContainText("Copy it now. It will not be shown again.");

    // Closing is destructive, so it is not a reflex click.
    const done = dialog.getByRole("button", { name: /discard from this screen/i });
    await expect(done).toBeDisabled();
    await dialog.locator("#qcp-confirm-phrase").fill("stored it");
    await expect(done).toBeEnabled();
    await done.click();
    await expect(dialog).toBeHidden();

    // Gone from the document the moment the dialog closes.
    expect((await page.content()).includes(plaintext)).toBe(false);

    // And gone after a reload: the server kept only a digest.
    await page.reload();
    await expect(card.getByText("Issued")).toBeVisible();
    expect((await page.content()).includes(plaintext)).toBe(false);

    // Nothing persisted it on the way past, either.
    const stored = await page.evaluate(() => ({
      local: JSON.stringify(window.localStorage),
      session: JSON.stringify(window.sessionStorage),
      cookie: document.cookie,
    }));
    expect(stored.local.includes(plaintext)).toBe(false);
    expect(stored.session.includes(plaintext)).toBe(false);
    expect(stored.cookie.includes(plaintext)).toBe(false);

    // Only the non-reversible prefix survives on screen.
    await expect(card).toContainText(world.product("quatapay")!.api_key_prefix);
  });

  test("rotating a live key confirms first, then shows the replacement once", async ({ page }) => {
    const world = await useWorld(
      page,
      freshWorld({
        products: [
          product(1, "quatapay", "QuataPay", {
            api_key_hash: "old",
            api_key_prefix: "qcp_oldpref",
            is_enabled: true,
          }),
        ],
      })
    );

    await page.goto("/admin/qcp/products");
    const card = page.locator("div.ring-soft.p-5").filter({ hasText: "QuataPay" });
    await card.getByRole("button", { name: /rotate key/i }).click();

    // Rotation kills the live key with no overlap window, so it is gated.
    const confirm = dialogOf(page);
    await expect(confirm).toContainText("The current key stops working the moment the new one is minted");
    await confirm.getByRole("button", { name: "Rotate key" }).click();

    const plaintext = world.mintedKeys[0];
    const minted = dialogOf(page);
    await expect(minted.locator("#minted-key")).toHaveText(plaintext);

    await minted.locator("#qcp-confirm-phrase").fill("stored it");
    await minted.getByRole("button", { name: /discard from this screen/i }).click();
    await expect(minted).toBeHidden();
    expect((await page.content()).includes(plaintext)).toBe(false);

    expect(requestsTo(world, "POST", "/admin/qcp/products/quatapay/api-key")).toHaveLength(1);
    await expect(card).toContainText(world.product("quatapay")!.api_key_prefix);
  });

  test("a keyless product cannot be enabled, and the backend refusal reads as a policy", async ({
    page,
  }) => {
    const world = freshWorld({ products: [product(1, "quatapay", "QuataPay")] });
    await useWorld(page, world);

    await page.goto("/admin/qcp/products");
    const card = page.locator("div.ring-soft.p-5").filter({ hasText: "QuataPay" });
    await card.getByRole("button", { name: /^Enable$/ }).click();

    const dialog = dialogOf(page);
    await expect(dialog).toContainText("no API key");
    await expect(dialog.getByRole("button", { name: "Enable product" })).toBeDisabled();
    await dialog.getByRole("button", { name: "Cancel" }).click();

    expect(requestsTo(world, "POST", "/admin/qcp/products/quatapay/enable")).toHaveLength(0);
    expect(world.product("quatapay")!.is_enabled).toBe(false);
  });

  test("the gateway's own refusal is relayed when the console thinks a key exists", async ({
    page,
  }) => {
    const world = freshWorld({
      products: [product(1, "quatapay", "QuataPay", { api_key_hash: "x", api_key_prefix: "qcp_quatapa" })],
    });
    world.forced.set("POST /admin/qcp/products/quatapay/enable", {
      status: 409,
      body: {
        detail: {
          reason: "no_api_key",
          message:
            "This product has no API key, so it cannot authenticate at the gateway. Mint one before enabling it.",
        },
      },
    });
    await useWorld(page, world);

    await page.goto("/admin/qcp/products");
    const card = page.locator("div.ring-soft.p-5").filter({ hasText: "QuataPay" });
    await card.getByRole("button", { name: /^Enable$/ }).click();
    await dialogOf(page).getByRole("button", { name: "Enable product" }).click();

    const banner = page.getByRole("alert").first();
    await expect(banner).toContainText(
      "This product has no API key, so it cannot authenticate at the gateway. Mint one before enabling it."
    );
    expect(world.product("quatapay")!.is_enabled).toBe(false);
  });
});

/* ========================================================================= */
/* 3b. Granting a product the authentication number                          */
/* ========================================================================= */

test.describe("QCP console — granting Quata Verify", () => {
  test("the grant is its own call, with its own justification", async ({ page }) => {
    const world = await useWorld(
      page,
      freshWorld({ products: [product(1, "quatapay", "QuataPay")] })
    );

    await page.goto("/admin/qcp/products");
    await page
      .locator("div.ring-soft.p-5")
      .filter({ hasText: "QuataPay" })
      .getByRole("button", { name: /reachable numbers/i })
      .click();

    const dialog = dialogOf(page);
    const save = dialog.getByRole("button", { name: "Save" });
    await expect(save).toBeDisabled(); // nothing changed yet

    await dialog.getByRole("checkbox").nth(1).check(); // Quata Verify
    await expect(dialog).toContainText("beside the fleet's OTP path");
    await expect(save).toBeDisabled(); // no justification yet

    await dialog.locator("#grant-justification").fill("short");
    await expect(save).toBeDisabled();

    await dialog
      .locator("#grant-justification")
      .fill("QuataPay is moving login OTP to QCP, approved 2026-08-11");
    await expect(save).toBeEnabled();
    await save.click();
    await expect(dialog).toBeHidden();

    const grants = requestsTo(world, "POST", "/admin/qcp/products/quatapay/purposes/authentication");
    expect(grants).toHaveLength(1);
    expect(grants[0].body).toEqual({
      justification: "QuataPay is moving login OTP to QCP, approved 2026-08-11",
    });
    // The grant already left the ceiling where it was asked for, so the
    // console must not follow it with a redundant PUT.
    expect(requestsTo(world, "PUT", "/admin/qcp/products/quatapay/purposes")).toHaveLength(0);
    expect(world.product("quatapay")!.allowed_purposes.sort()).toEqual([
      "authentication",
      "engagement",
    ]);
  });

  test("granting and narrowing in one edit takes both calls, in order", async ({ page }) => {
    const world = await useWorld(
      page,
      freshWorld({ products: [product(1, "quatapay", "QuataPay")] })
    );

    await page.goto("/admin/qcp/products");
    await page
      .locator("div.ring-soft.p-5")
      .filter({ hasText: "QuataPay" })
      .getByRole("button", { name: /reachable numbers/i })
      .click();

    const dialog = dialogOf(page);
    await dialog.getByRole("checkbox").nth(1).check(); // + Quata Verify
    await dialog.getByRole("checkbox").nth(0).uncheck(); // − QUATA
    await dialog
      .locator("#grant-justification")
      .fill("QuataPay becomes authentication-only on QCP, approved 2026-08-11");
    await dialog.getByRole("button", { name: "Save" }).click();
    await expect(dialog).toBeHidden();

    // `PUT purposes` may narrow but may never add authentication, so the
    // grant has to land first or the narrowing is refused.
    const qcp = world.requests.filter((r) => r.path.startsWith("/admin/qcp/products/quatapay/purposes"));
    expect(qcp.map((r) => `${r.method} ${r.path}`)).toEqual([
      "POST /admin/qcp/products/quatapay/purposes/authentication",
      "PUT /admin/qcp/products/quatapay/purposes",
    ]);
    expect(qcp[1].body).toEqual({ purposes: ["authentication"] });
    expect(world.product("quatapay")!.allowed_purposes).toEqual(["authentication"]);
  });
});

/* ========================================================================= */
/* 4. The category / number pairing                                          */
/* ========================================================================= */

test.describe("QCP console — template separation", () => {
  test("an illegal category/number pairing is refused in the form, with a reason", async ({
    page,
  }) => {
    const world = await useWorld(
      page,
      freshWorld({ products: [product(1, "quatapay", "QuataPay")] })
    );

    await page.goto("/admin/qcp/templates");
    await page.getByRole("button", { name: /new template/i }).click();

    const dialog = dialogOf(page);
    const submit = dialog.getByRole("button", { name: "Create template" });

    // A utility template on QUATA is legal.
    await dialog.locator("#category").selectOption("utility");
    await dialog.locator("#account").selectOption("quata");
    await expect(submit).toBeEnabled();

    // Re-categorising it to authentication strands it on the wrong number.
    await dialog.locator("#category").selectOption("authentication");
    await expect(dialog).toContainText(
      "An authentication template cannot live on QUATA. Security codes go out on Quata Verify and nowhere else."
    );
    await expect(submit).toBeDisabled();
    // The broken pairing stays visible rather than silently snapping elsewhere.
    await expect(
      dialog.locator("#account option", { hasText: "not allowed for authentication" })
    ).toHaveCount(1);

    // Marketing is never offered Quata Verify at all.
    await dialog.locator("#category").selectOption("marketing");
    const marketingOptions = await dialog.locator("#account option").allTextContents();
    expect(marketingOptions.join("|")).not.toContain("Quata Verify (authentication)");

    // Authentication offers Quata Verify and nothing else — the only other
    // entry is the stranded QUATA selection, kept visible but disabled.
    await dialog.locator("#category").selectOption("authentication");
    const authOptions = (await dialog.locator("#account option").allTextContents()).filter(
      (t) => !t.startsWith("—")
    );
    expect(authOptions).toEqual([
      "Quata Verify (authentication)",
      "QUATA — not allowed for authentication",
    ]);
    await expect(
      dialog.locator("#account option", { hasText: "not allowed for authentication" })
    ).toBeDisabled();

    // Nothing was ever sent while the form was in a refused state.
    expect(requestsTo(world, "POST", "/admin/qcp/templates")).toHaveLength(0);

    // Fixing the pairing makes it writable.
    await dialog.locator("#account").selectOption("quata-verify");
    await dialog.locator("#name").fill("otp_login_code");
    await dialog.locator("#intent").fill("login_otp");
    await dialog.locator("#body").fill("Your {{1}} code is {{2}}.");
    await expect(submit).toBeEnabled();
    await submit.click();
    await expect(dialog).toBeHidden();

    const posts = requestsTo(world, "POST", "/admin/qcp/templates");
    expect(posts).toHaveLength(1);
    expect(posts[0].body).toMatchObject({
      account: "quata-verify",
      category: "authentication",
      name: "otp_login_code",
      intent: "login_otp",
    });
  });

  test("a separation refusal from the backend is headlined as a policy decision", async ({
    page,
  }) => {
    const world = freshWorld();
    world.forced.set("POST /admin/qcp/templates", {
      status: 409,
      body: {
        detail: {
          reason: "non_auth_category_on_verify",
          detail:
            "Quata Verify carries the authentication category and nothing else, not even utility. Put this utility template on QUATA.",
        },
      },
    });
    await useWorld(page, world);

    await page.goto("/admin/qcp/templates");
    await page.getByRole("button", { name: /new template/i }).click();

    const dialog = dialogOf(page);
    await dialog.locator("#category").selectOption("utility");
    await dialog.locator("#account").selectOption("quata");
    await dialog.locator("#name").fill("order_update");
    await dialog.locator("#intent").fill("order_update");
    await dialog.locator("#body").fill("Order {{1}} is on its way.");
    await dialog.getByRole("button", { name: "Create template" }).click();

    const banner = dialog.getByRole("alert");
    await expect(banner).toContainText("Refused — that category cannot live on Quata Verify");
    await expect(banner).toContainText("not even utility");
    await expect(banner).toContainText("Nothing was written.");
    expect(world.templates).toHaveLength(0);
  });
});

/* ========================================================================= */
/* 5. The empty state — what the first operator actually meets               */
/* ========================================================================= */

const SCREENS = [
  { path: "/admin/qcp", ready: "QCP is dormant" },
  { path: "/admin/qcp/conversations", ready: "No conversations yet" },
  { path: "/admin/qcp/templates", ready: "No templates on this number yet" },
  { path: "/admin/qcp/routing", ready: "No routing rules" },
  { path: "/admin/qcp/products", ready: "No products registered" },
];

test.describe("QCP console — the shipped, empty state", () => {
  test("every screen reads as correctly empty, not as broken", async ({ page }) => {
    const crashes = watchForCrashes(page);
    const world = await useWorld(page, freshWorld());

    for (const screen of SCREENS) {
      await page.goto(screen.path);
      await expect(
        page.getByText(screen.ready).first(),
        `${screen.path} did not reach its empty state`
      ).toBeVisible();

      // "Empty" must never be dressed up as a failure to load, and must never
      // be left as a spinner.
      await expect(page.getByText("Couldn't load this screen")).toHaveCount(0);
      await expect(page.getByText(/^Loading/)).toHaveCount(0);
    }

    // The overview explains dormancy rather than showing a red light.
    await page.goto("/admin/qcp");
    await expect(page.getByText("Nothing is being sent. This is the shipped state.")).toBeVisible();
    await expect(page.getByText("Dormant is correct until a product is explicitly migrated.")).toBeVisible();
    await expect(page.getByText("No products registered").first()).toBeVisible();
    await expect(page.getByText("Nothing has failed")).toBeVisible();
    await expect(page.getByText("No denials recorded")).toBeVisible();

    // The registry says why "nothing here" is the right answer.
    await page.goto("/admin/qcp/products");
    await expect(
      page.getByText(/which is the correct state for a platform no product has migrated to yet/)
    ).toBeVisible();

    // Routing offers the vocabulary rather than an error.
    await page.goto("/admin/qcp/routing");
    await expect(page.getByText(/With every product disabled that is the correct state/)).toBeVisible();

    expect(crashes).toEqual([]);
    expect(world.unhandled, "the console called an endpoint the fake does not model").toEqual([]);
  });

  test("with no accounts seeded, each screen says the seed has not run", async ({ page }) => {
    const crashes = watchForCrashes(page);
    await useWorld(page, barrenWorld());

    await page.goto("/admin/qcp");
    await expect(page.getByText("No accounts registered")).toBeVisible();
    await expect(page.getByText(/the seed has not run against this database/i).first()).toBeVisible();

    await page.goto("/admin/qcp/templates");
    await expect(page.getByText("No accounts registered")).toBeVisible();
    // Nothing to create a template against, so the control is not offered.
    await expect(page.getByRole("button", { name: /new template/i })).toBeDisabled();

    await page.goto("/admin/qcp/routing");
    await expect(page.getByText("No routing rules")).toBeVisible();
    await expect(page.getByRole("button", { name: /new rule/i })).toBeDisabled();

    await page.goto("/admin/qcp/products");
    await expect(page.getByText("No products registered")).toBeVisible();

    await page.goto("/admin/qcp/conversations");
    await expect(page.getByText("No conversations yet")).toBeVisible();

    expect(crashes).toEqual([]);
  });
});
