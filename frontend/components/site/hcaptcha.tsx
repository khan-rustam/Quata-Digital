"use client";

import * as React from "react";

/**
 * Lightweight hCaptcha widget. Loads the official script on first mount
 * and exposes the verification token via the `onVerify` callback.
 *
 * No-op when `NEXT_PUBLIC_HCAPTCHA_SITE_KEY` is not configured — the form
 * still works, the captcha just doesn't render. The backend mirrors this
 * behaviour: if the secret is unset, captcha is bypassed.
 */
declare global {
  interface Window {
    hcaptcha?: {
      render: (
        el: HTMLElement,
        opts: {
          sitekey: string;
          callback: (token: string) => void;
          "expired-callback"?: () => void;
          "error-callback"?: () => void;
          theme?: "light" | "dark";
        }
      ) => string;
      reset: (id?: string) => void;
      remove: (id?: string) => void;
    };
  }
}

const SITE_KEY = process.env.NEXT_PUBLIC_HCAPTCHA_SITE_KEY ?? "";
const SCRIPT_ID = "hcaptcha-script";

let scriptPromise: Promise<void> | null = null;

function loadHCaptcha(): Promise<void> {
  if (typeof window === "undefined") return Promise.resolve();
  if (window.hcaptcha) return Promise.resolve();
  if (scriptPromise) return scriptPromise;
  scriptPromise = new Promise((resolve, reject) => {
    if (document.getElementById(SCRIPT_ID)) {
      resolve();
      return;
    }
    const s = document.createElement("script");
    s.id = SCRIPT_ID;
    s.src = "https://js.hcaptcha.com/1/api.js?render=explicit";
    s.async = true;
    s.defer = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error("Failed to load hCaptcha"));
    document.head.appendChild(s);
  });
  return scriptPromise;
}

export function HCaptcha({
  onVerify,
  onExpire,
  className,
}: {
  onVerify: (token: string) => void;
  onExpire?: () => void;
  className?: string;
}) {
  const ref = React.useRef<HTMLDivElement | null>(null);
  const widgetIdRef = React.useRef<string | null>(null);
  const onVerifyRef = React.useRef(onVerify);
  const onExpireRef = React.useRef(onExpire);
  // Keep latest callbacks in refs without re-rendering the captcha widget.
  React.useEffect(() => {
    onVerifyRef.current = onVerify;
  }, [onVerify]);
  React.useEffect(() => {
    onExpireRef.current = onExpire;
  }, [onExpire]);

  React.useEffect(() => {
    if (!SITE_KEY || !ref.current) return;
    let mounted = true;
    loadHCaptcha()
      .then(() => {
        if (!mounted || !ref.current || !window.hcaptcha) return;
        widgetIdRef.current = window.hcaptcha.render(ref.current, {
          sitekey: SITE_KEY,
          callback: (token) => onVerifyRef.current(token),
          "expired-callback": () => onExpireRef.current?.(),
        });
      })
      .catch(() => {
        // The form will still submit; the server will accept since secret
        // is also unset, or reject if secret is set — handled there.
      });
    return () => {
      mounted = false;
      if (widgetIdRef.current && window.hcaptcha) {
        try {
          window.hcaptcha.remove(widgetIdRef.current);
        } catch {
          // ignore
        }
      }
    };
  }, []);

  if (!SITE_KEY) return null;
  return <div ref={ref} className={className} />;
}

export const captchaConfigured = Boolean(SITE_KEY);
