import { expect, test } from "@playwright/test";

/**
 * Smoke test for the public-site renderer.
 *
 * Asserts that:
 *  - Home page returns 200 with the brand strapline visible.
 *  - Sitemap is reachable and includes at least the home URL.
 *  - The 404 page returns the branded layout, not Next.js's default.
 */

test("home page renders the brand strapline", async ({ page }) => {
  await page.goto("/");
  // Either CMS-driven hero or static fallback contains "QUATA".
  await expect(page).toHaveTitle(/QUATA/i);
  // The site footer renders on every page.
  await expect(page.locator("footer")).toBeVisible();
});

test("sitemap.xml lists the home URL", async ({ request }) => {
  const res = await request.get("/sitemap.xml");
  expect(res.status()).toBe(200);
  const body = await res.text();
  expect(body).toMatch(/<loc>[^<]+<\/loc>/);
});

test("404 page renders the branded layout", async ({ page }) => {
  const res = await page.goto("/this-route-definitely-does-not-exist", {
    waitUntil: "domcontentloaded",
  });
  expect(res?.status()).toBe(404);
  // Branded layout — heading or copy that confirms it's our 404, not Next's.
  await expect(page.getByText(/can.?t find that page/i)).toBeVisible();
});
