import { AlertTriangle } from "lucide-react";

import { getSiteSettings } from "@/lib/site-settings";

const DEFAULT_MESSAGE =
  "QUATA Digital is currently undergoing scheduled maintenance. Some features may be briefly unavailable.";

/**
 * Top-of-page banner shown only when `toggles.maintenance_mode` is ON in
 * Site settings. Server-rendered in the public layout — invisible on the
 * admin shell, which uses a different layout.
 */
export async function MaintenanceBanner() {
  const settings = await getSiteSettings();
  if (!settings.toggles.maintenance_mode) return null;
  const message = settings.toggles.maintenance_message ?? DEFAULT_MESSAGE;
  return (
    <div
      role="status"
      className="border-b border-amber-200 bg-amber-50 text-amber-900"
    >
      <div className="container-page flex items-start gap-3 py-2.5 text-xs sm:text-sm">
        <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
        <span className="leading-relaxed">{message}</span>
      </div>
    </div>
  );
}
