// k6 launch-day load test.
//
// Usage:
//   k6 run -u 50 -d 60s -e BASE_URL=https://staging.quatadigital.com scripts/load/launch.js
//
// Targets the highest-volume public endpoints:
//   GET  /products
//   POST /track          (page-view tracker)
//   GET  /search?q=...   (the public search bar)
//   POST /contact        (rate-limited; bursts will surface 429s)
//
// Validates:
//   - p95 < 500 ms across the mix
//   - Error rate < 1% (excluding the deliberate rate-limit pressure path)

import http from "k6/http";
import { check, group, sleep } from "k6";
import { Rate } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const API = `${BASE_URL.replace(/\/$/, "")}/api/v1`;

const errorRate = new Rate("custom_errors");

export const options = {
  thresholds: {
    http_req_duration: ["p(95)<500"],
    custom_errors: ["rate<0.01"],
  },
};

const SEARCH_TERMS = [
  "quatapay",
  "abaqwa",
  "merchant",
  "partnerships",
  "wallet",
];

function pick(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

export default function () {
  group("read-heavy (90% of traffic)", () => {
    const products = http.get(`${API}/products`);
    check(products, { "products 200": (r) => r.status === 200 }) ||
      errorRate.add(1);

    const search = http.get(
      `${API}/search?q=${encodeURIComponent(pick(SEARCH_TERMS))}`
    );
    check(search, { "search 200": (r) => r.status === 200 }) ||
      errorRate.add(1);

    const track = http.post(
      `${API}/track`,
      JSON.stringify({
        path: "/about",
        referrer: "https://google.com",
        visitor_id: `vu_${__VU}`,
      }),
      { headers: { "Content-Type": "application/json" } }
    );
    check(track, { "track 204": (r) => r.status === 204 }) ||
      errorRate.add(1);
  });

  // 1-in-30 iterations submits a contact form. Below the 20/min rate
  // limit per IP at 50 VUs, but tight enough to exercise the path.
  if (Math.random() < 1 / 30) {
    group("contact submit", () => {
      const r = http.post(
        `${API}/contact`,
        JSON.stringify({
          name: `Load Test ${__VU}`,
          email: `vu${__VU}+loadtest@example.com`,
          reason: "General",
          message: `Hello from VU ${__VU}, iteration ${__ITER}.`,
        }),
        { headers: { "Content-Type": "application/json" } }
      );
      // 201 on accept, 429 if we hit the rate-limit — both expected.
      check(r, { "contact 201 or 429": (r) => r.status === 201 || r.status === 429 });
    });
  }

  sleep(1);
}
