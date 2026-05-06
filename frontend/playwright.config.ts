import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright E2E config.
 *
 * Local dev:
 *   1. Make sure the backend is running (uvicorn :8000) and seeded.
 *   2. Run `npm run dev` in another terminal so Next is on :3000.
 *   3. `npm run e2e` to execute the suite.
 *
 * In CI we'll point `BASE_URL` at a deploy preview / staging URL and
 * skip `webServer` entirely — see .github/workflows/ci.yml when this
 * is wired into CI (left as a follow-up so the preview URL convention
 * lands first).
 *
 * Tests live under `e2e/` so they're easy to spot. The suite is
 * deliberately tiny — one happy-path smoke per critical flow.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false, // serial keeps the seeded admin sane between specs
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    locale: "en-GB",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  expect: {
    timeout: 10_000,
  },
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        command: "npm run dev",
        url: "http://localhost:3000",
        reuseExistingServer: true,
        timeout: 120_000,
      },
});
