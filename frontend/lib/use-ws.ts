"use client";

import * as React from "react";
import { useAuth } from "./auth";

export type WsEvent = {
  type: string;
  [key: string]: unknown;
};

type Status = "idle" | "connecting" | "open" | "closed" | "error";

const HTTP_API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

function wsBase(): string {
  // /api/v1/... -> ws(s)://host/ws/messages
  try {
    const u = new URL(HTTP_API_URL);
    const proto = u.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${u.host}`;
  } catch {
    return "ws://localhost:8000";
  }
}

export function useWebSocket(path: string, opts: { onMessage?: (e: WsEvent) => void } = {}) {
  const { token } = useAuth();
  const [status, setStatus] = React.useState<Status>("idle");
  const [last, setLast] = React.useState<WsEvent | null>(null);
  const sockRef = React.useRef<WebSocket | null>(null);
  const onMessageRef = React.useRef(opts.onMessage);
  // Keep the latest callback in a ref without re-binding the WebSocket.
  React.useEffect(() => {
    onMessageRef.current = opts.onMessage;
  }, [opts.onMessage]);

  React.useEffect(() => {
    if (!token) return;
    let cancelled = false;
    let reconnectTimer: number | null = null;

    function connect() {
      if (cancelled) return;
      setStatus("connecting");
      const ws = new WebSocket(`${wsBase()}${path}?token=${encodeURIComponent(token!)}`);
      sockRef.current = ws;

      ws.onopen = () => setStatus("open");
      ws.onclose = () => {
        setStatus("closed");
        if (!cancelled) reconnectTimer = window.setTimeout(connect, 3000);
      };
      ws.onerror = () => setStatus("error");
      ws.onmessage = (ev) => {
        try {
          const data: WsEvent = JSON.parse(ev.data);
          setLast(data);
          onMessageRef.current?.(data);
        } catch {
          // ignore non-JSON frames
        }
      };
    }

    connect();
    return () => {
      cancelled = true;
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      if (sockRef.current && sockRef.current.readyState <= 1) sockRef.current.close();
    };
  }, [token, path]);

  return { status, last };
}
