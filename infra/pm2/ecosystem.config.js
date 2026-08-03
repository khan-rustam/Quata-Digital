/**
 * QUATA Digital — PM2 ecosystem config for the Next.js frontend.
 *
 * Install / start:
 *   pm2 start infra/pm2/ecosystem.config.js
 *   pm2 save
 *   pm2 startup        # one-time, to install the systemd shim
 *
 * Reload (zero-downtime):
 *   pm2 reload QuataDigital-F
 *
 * Logs:
 *   pm2 logs QuataDigital-F
 *
 * The app name MUST match what deploy.sh restarts ("QuataDigital-F") and the
 * name already live in PM2. It used to say "Quata-Digi-F" here, which meant
 * `pm2 start` from this file would create a SECOND app on port 3500 beside the
 * running one. That exact mismatch is what broke ntaccul on 2026-07-30: two PM2
 * entries for one port, the deploy reloading the one that could not bind, and
 * the stale process serving on while every deploy reported success.
 */
module.exports = {
  apps: [
    {
      name: "QuataDigital-F",
      // Post-relocation path. This said /home/Quata-Digital/frontend, which has
      // not existed since the move to /var/www/Projects — starting from this
      // file would have failed outright.
      cwd: "/var/www/Projects/Quata-Digital/frontend",
      // frontend/next.config sets `output: "standalone"`, which Next does not
      // support under `next start` (what `npm start` runs) — it warns on every
      // boot and serves a .next/ tree that the next build overwrites beneath
      // the live process. Point pm2 at the standalone server instead.
      //
      // The standalone server reads PORT + HOSTNAME from the env below rather
      // than CLI flags, and it calls process.chdir(__dirname) itself. Note
      // this makes HOSTNAME actually take effect: `next start` ignored it and
      // bound 0.0.0.0, so the app will now bind 127.0.0.1 as declared here —
      // which is what nginx proxies to.
      //
      // deploy.sh copies .next/static + public/ in after each build; Next
      // does not do that itself and without it every client asset 404s.
      script: ".next/standalone/server.js",
      exec_mode: "cluster",
      instances: 2,
      autorestart: true,
      max_memory_restart: "768M",
      // Tell next-server which port to bind.
      env: {
        NODE_ENV: "production",
        PORT: "3500",
        HOSTNAME: "127.0.0.1",
        NEXT_TELEMETRY_DISABLED: "1",
        // Cap the V8 heap so a runaway build/render path can't take
        // down the whole VPS — PM2 will restart the worker first.
        NODE_OPTIONS: "--max-old-space-size=768",
      },
      time: true,
      log_date_format: "YYYY-MM-DD HH:mm:ss Z",
    },
  ],
};
