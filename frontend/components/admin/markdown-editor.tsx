"use client";

/**
 * Markdown editor with a toolbar, image upload and live preview.
 *
 * Used by:
 *  - Blog post editor (admin/cms — body field)
 *  - CMS page editor (admin/cms — page content field)
 *  - Newsletter broadcast composer (admin/newsletter/broadcast)
 *
 * Pragmatic Option A per the locked plan: keep the underlying field as a
 * markdown <textarea>, just give the writer better ergonomics. Block-based
 * (TipTap) is a v2 once we see how this is used.
 */

import * as React from "react";
import {
  Bold,
  Italic,
  Heading2,
  Heading3,
  Link2,
  List,
  ListOrdered,
  Quote,
  Code,
  ImageIcon,
  Eye,
  Pencil,
  Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Textarea } from "@/components/ui/textarea";
import { MarkdownPreview } from "./markdown";
import { apiUrl } from "@/lib/api";

type Mode = "write" | "preview" | "split";

export function MarkdownEditor({
  value,
  onChange,
  placeholder = "Write in markdown — toolbar above helps with the basics.",
  rows = 14,
  name,
  className,
  defaultMode = "split",
  imageFolder = "cms",
}: {
  value: string;
  onChange: (next: string) => void;
  placeholder?: string;
  rows?: number;
  name?: string;
  className?: string;
  defaultMode?: Mode;
  imageFolder?: string;
}) {
  const [mode, setMode] = React.useState<Mode>(defaultMode);
  const [uploading, setUploading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const ref = React.useRef<HTMLTextAreaElement>(null);
  const fileRef = React.useRef<HTMLInputElement>(null);

  /** Wrap or insert markdown around the current selection. */
  function applyWrap(before: string, after = before, placeholderText = "") {
    const ta = ref.current;
    if (!ta) return;
    const start = ta.selectionStart ?? 0;
    const end = ta.selectionEnd ?? 0;
    const selected = value.slice(start, end) || placeholderText;
    const next =
      value.slice(0, start) + before + selected + after + value.slice(end);
    onChange(next);
    // Re-focus and re-select the inserted text so the writer can keep typing.
    requestAnimationFrame(() => {
      ta.focus();
      ta.setSelectionRange(
        start + before.length,
        start + before.length + selected.length,
      );
    });
  }

  /** Insert at the start of the current line. */
  function applyLinePrefix(prefix: string) {
    const ta = ref.current;
    if (!ta) return;
    const pos = ta.selectionStart ?? 0;
    const lineStart = value.lastIndexOf("\n", pos - 1) + 1;
    const next = value.slice(0, lineStart) + prefix + value.slice(lineStart);
    onChange(next);
    requestAnimationFrame(() => {
      ta.focus();
      ta.setSelectionRange(pos + prefix.length, pos + prefix.length);
    });
  }

  /** Insert raw text at cursor. */
  function insertAtCursor(text: string) {
    const ta = ref.current;
    if (!ta) return;
    const pos = ta.selectionStart ?? value.length;
    const next = value.slice(0, pos) + text + value.slice(pos);
    onChange(next);
    requestAnimationFrame(() => {
      ta.focus();
      ta.setSelectionRange(pos + text.length, pos + text.length);
    });
  }

  function promptLink() {
    const url = window.prompt("Link URL", "https://");
    if (!url) return;
    applyWrap("[", `](${url})`, "link text");
  }

  async function uploadImage(file: File) {
    setUploading(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("folder", imageFolder);
      const headers: Record<string, string> = {};
      const token =
        typeof window !== "undefined" ? localStorage.getItem("quata_token") : null;
      if (token) headers.Authorization = `Bearer ${token}`;
      const res = await fetch(`${apiUrl}/uploads`, {
        method: "POST",
        body: fd,
        headers,
      });
      if (!res.ok) {
        let detail = res.statusText;
        try {
          detail = (await res.json()).detail ?? detail;
        } catch {}
        throw new Error(detail);
      }
      const data: { url: string; filename: string } = await res.json();
      const alt = file.name.replace(/\.[^.]+$/, "");
      insertAtCursor(`\n\n![${alt}](${data.url})\n\n`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <div className={cn("rounded-xl border border-border bg-surface overflow-hidden", className)}>
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-1 border-b border-border bg-surface-soft px-2 py-2">
        <ToolbarButton title="Heading 2" onClick={() => applyLinePrefix("## ")}>
          <Heading2 className="h-3.5 w-3.5" />
        </ToolbarButton>
        <ToolbarButton title="Heading 3" onClick={() => applyLinePrefix("### ")}>
          <Heading3 className="h-3.5 w-3.5" />
        </ToolbarButton>
        <Sep />
        <ToolbarButton title="Bold" onClick={() => applyWrap("**", "**", "bold text")}>
          <Bold className="h-3.5 w-3.5" />
        </ToolbarButton>
        <ToolbarButton title="Italic" onClick={() => applyWrap("*", "*", "italic text")}>
          <Italic className="h-3.5 w-3.5" />
        </ToolbarButton>
        <ToolbarButton title="Inline code" onClick={() => applyWrap("`", "`", "code")}>
          <Code className="h-3.5 w-3.5" />
        </ToolbarButton>
        <Sep />
        <ToolbarButton title="Bulleted list" onClick={() => applyLinePrefix("- ")}>
          <List className="h-3.5 w-3.5" />
        </ToolbarButton>
        <ToolbarButton title="Numbered list" onClick={() => applyLinePrefix("1. ")}>
          <ListOrdered className="h-3.5 w-3.5" />
        </ToolbarButton>
        <ToolbarButton title="Blockquote" onClick={() => applyLinePrefix("> ")}>
          <Quote className="h-3.5 w-3.5" />
        </ToolbarButton>
        <Sep />
        <ToolbarButton title="Insert link" onClick={promptLink}>
          <Link2 className="h-3.5 w-3.5" />
        </ToolbarButton>
        <ToolbarButton
          title="Upload image"
          onClick={() => fileRef.current?.click()}
          disabled={uploading}
        >
          {uploading ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <ImageIcon className="h-3.5 w-3.5" />
          )}
        </ToolbarButton>
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          className="sr-only"
          onChange={(e) => e.target.files?.[0] && uploadImage(e.target.files[0])}
        />

        {/* Mode switcher pushed right */}
        <div className="ml-auto inline-flex items-center rounded-lg border border-border bg-surface p-0.5 text-xs">
          <ModeButton current={mode} mode="write" onClick={() => setMode("write")}>
            <Pencil className="h-3 w-3" /> Write
          </ModeButton>
          <ModeButton current={mode} mode="split" onClick={() => setMode("split")}>
            Split
          </ModeButton>
          <ModeButton current={mode} mode="preview" onClick={() => setMode("preview")}>
            <Eye className="h-3 w-3" /> Preview
          </ModeButton>
        </div>
      </div>

      {/* Editor body */}
      <div
        className={cn(
          "grid",
          mode === "split" ? "lg:grid-cols-2 divide-x divide-border" : "grid-cols-1",
        )}
      >
        {(mode === "write" || mode === "split") && (
          <Textarea
            ref={ref}
            value={value}
            name={name}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            rows={rows}
            className="rounded-none border-0 bg-card font-mono text-[13px] leading-relaxed focus-visible:ring-0 focus-visible:ring-offset-0 resize-y"
          />
        )}
        {(mode === "preview" || mode === "split") && (
          <div className="bg-card p-4 overflow-auto" style={{ minHeight: rows * 22 }}>
            <MarkdownPreview source={value} />
          </div>
        )}
      </div>

      {error && (
        <div className="border-t border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-900">
          {error}
        </div>
      )}
    </div>
  );
}

function Sep() {
  return <span className="mx-1 h-4 w-px bg-border" aria-hidden />;
}

function ToolbarButton({
  title,
  onClick,
  children,
  disabled,
}: {
  title: string;
  onClick: () => void;
  children: React.ReactNode;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      disabled={disabled}
      className="inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:bg-secondary hover:text-foreground disabled:opacity-40 disabled:cursor-not-allowed"
    >
      {children}
      <span className="sr-only">{title}</span>
    </button>
  );
}

function ModeButton({
  current,
  mode,
  onClick,
  children,
}: {
  current: Mode;
  mode: Mode;
  onClick: () => void;
  children: React.ReactNode;
}) {
  const active = current === mode;
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1 rounded-md px-2 py-1 transition",
        active
          ? "bg-primary text-primary-foreground"
          : "text-muted-foreground hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}

// Re-export for convenience (callers that need both).
export { MarkdownPreview };
