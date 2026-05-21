/**
 * QUATA Digital — PM2 ecosystem config for the Next.js frontend.
 *
 * Install / start:
 *   pm2 start infra/pm2/ecosystem.config.js
 *   pm2 save
 *   pm2 startup        # one-time, to install the systemd shim
 *
 * Reload (zero-downtime):
 *   pm2 reload Quata-Digi-F
 *
 * Logs:
 *   pm2 logs Quata-Digi-F
 */
module.exports = {
  apps: [
    {
      name: "Quata-Digi-F",
      cwd: "/home/Quata-Digital/frontend",
      // Cluster mode + `reload` gives us rolling restarts.
      script: "npm",
      args: "start",
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
