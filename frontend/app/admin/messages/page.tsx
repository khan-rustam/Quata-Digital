"use client";

import * as React from "react";
import { Send, Paperclip } from "lucide-react";
import { PageShell } from "@/components/admin/page-shell";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { useApi, useApiAction } from "@/lib/use-api";
import { useToast } from "@/components/ui/toast";
import { useWebSocket } from "@/lib/use-ws";
import { LiveIndicator } from "@/components/admin/live-indicator";

type Message = {
  id: number;
  subject: string;
  body: string;
  audience: "all" | "department" | "individual";
  message_type: "general" | "announcement" | "urgent";
  department: string | null;
  recipient: string | null;
  read_count: number;
  total_recipients: number;
  created_at: string;
  author: string;
};

const typeVariant = {
  general: "outline",
  announcement: "brand",
  urgent: "danger",
} as const;

export default function MessagesPage() {
  const { data, loading, refresh } = useApi<Message[]>("/admin/messages");
  const departments = useApi<{ id: number; name: string; slug: string }[]>("/admin/departments");
  const action = useApiAction();
  const toast = useToast();
  const [sending, setSending] = React.useState(false);

  // Live updates: refresh when a new message arrives over WebSocket
  const ws = useWebSocket("/ws/messages", {
    onMessage: (ev) => {
      if (ev.type === "message") {
        toast.info("New message", String(ev.subject ?? ""));
        refresh();
      }
    },
  });

  async function onSend(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSending(true);
    const formData = Object.fromEntries(new FormData(e.currentTarget).entries());
    try {
      await action("/admin/messages", { method: "POST", body: JSON.stringify(formData) });
      (e.target as HTMLFormElement).reset();
      toast.success("Message sent");
      refresh();
    } catch (err) {
      toast.error("Couldn't send", err instanceof Error ? err.message : "Try again.");
    } finally {
      setSending(false);
    }
  }

  return (
    <PageShell
      title="Internal communications"
      description="Send announcements, urgent notices or general messages to staff, departments or individuals."
      actions={<LiveIndicator status={ws.status} />}
    >
      <div className="grid lg:grid-cols-3 gap-6">
        <form onSubmit={onSend} className="lg:col-span-1 rounded-2xl border border-border bg-card p-5 ring-soft grid gap-4 self-start">
          <div className="text-sm font-semibold">New message</div>
          <div className="grid gap-2">
            <Label htmlFor="subject">Subject</Label>
            <Input id="subject" name="subject" required placeholder="Friday all-hands at 4pm" />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="grid gap-2">
              <Label htmlFor="audience">Audience</Label>
              <Select id="audience" name="audience" defaultValue="all">
                <option value="all">All staff</option>
                <option value="department">Department</option>
                <option value="individual">Individual</option>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="message_type">Type</Label>
              <Select id="message_type" name="message_type" defaultValue="general">
                <option value="general">General</option>
                <option value="announcement">Announcement</option>
                <option value="urgent">Urgent</option>
              </Select>
            </div>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="department">Department (if scoped)</Label>
            <Select id="department" name="department_slug" defaultValue="">
              <option value="">—</option>
              {(departments.data ?? []).map((d) => (
                <option key={d.id} value={d.slug}>
                  {d.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="body">Message</Label>
            <Textarea id="body" name="body" rows={6} required placeholder="Type your message here. Markdown supported." />
          </div>
          <div className="flex items-center justify-between">
            <Button variant="ghost" size="sm" type="button">
              <Paperclip className="h-3.5 w-3.5" /> Attach
            </Button>
            <Button type="submit" disabled={sending}>
              <Send className="h-4 w-4" />
              Send
            </Button>
          </div>
        </form>

        <div className="lg:col-span-2 grid gap-3">
          <div className="text-sm font-semibold">Sent messages</div>
          {loading && <div className="text-sm text-muted-foreground">Loading…</div>}
          {(data ?? []).map((m) => (
            <div key={m.id} className="rounded-2xl border border-border bg-card p-5 ring-soft">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-base font-semibold">{m.subject}</div>
                  <div className="text-xs text-muted-foreground mt-1">
                    From {m.author} ·{" "}
                    {m.audience === "all"
                      ? "All staff"
                      : m.audience === "department"
                      ? `Dept: ${m.department}`
                      : `To ${m.recipient}`}
                    {" · "}
                    {new Date(m.created_at).toLocaleString()}
                  </div>
                </div>
                <Badge variant={typeVariant[m.message_type]} className="capitalize">
                  {m.message_type}
                </Badge>
              </div>
              <p className="mt-3 text-sm text-foreground/80 whitespace-pre-line line-clamp-3">{m.body}</p>
              <div className="mt-4 text-xs text-muted-foreground">
                Read by {m.read_count}/{m.total_recipients}
              </div>
            </div>
          ))}
        </div>
      </div>
    </PageShell>
  );
}
