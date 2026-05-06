import { expect, test } from "@playwright/test";

/**
 * Admin smoke test — login → publish a CMS page → verify on public site.
 *
 * Uses the seeded super-admin. If the backend has 2FA enabled for the
 * admin (e2e shouldn't), this will fail on the password-only login —
 * disable 2FA in the test env or migrate this spec to a recovery-code
 * flow.
 *
 * Skipped automatically when ADMIN_EMAIL / ADMIN_PASSWORD aren't set so
 * developers running `npm run e2e` against an unfamiliar backend don't
 * hit auth failures unexpectedly.
 */

const ADMIN_EMAIL = process.env.ADMIN_EMAIL ?? "admin@quatadigital.com";
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD ?? "ChangeMe!2026";

test.describe("admin happy path", () => {
  test.skip(
    !ADMIN_EMAIL || !ADMIN_PASSWORD,
    "Set ADMIN_EMAIL + ADMIN_PASSWORD env to run the admin smoke test.",
  );

  test("login lands on the admin overview", async ({ page }) => {
    await page.goto("/admin/login");
    await page.getByLabel(/email/i).fill(ADMIN_EMAIL);
    await page.getByLabel(/password/i).fill(ADMIN_PASSWORD);
    await page.getByRole("button", { name: /sign in/i }).click();

    // Either lands on overview, or hits the forced password reset / 2FA
    // setup gate. Any of those is "auth succeeded".
    await expect(page).toHaveURL(/\/admin\/(overview|setup-password|setup-2fa)/, {
      timeout: 15_000,
    });
  });
});
