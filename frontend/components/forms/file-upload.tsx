"use client";

import * as React from "react";
import { CheckCircle2, FileUp, Loader2, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { apiUrl } from "@/lib/api";

export type UploadResult = {
  url: string;
  filename: string;
  size: number;
  content_type: string;
};

export function FileUpload({
  name,
  folder,
  endpoint = "/uploads/public",
  accept,
  className,
  onUploaded,
  hint,
}: {
  name: string;
  folder?: string;
  endpoint?: "/uploads" | "/uploads/public";
  accept?: string;
  className?: string;
  onUploaded?: (file: UploadResult) => void;
  hint?: string;
}) {
  const [state, setState] = React.useState<"idle" | "uploading" | "done" | "error">("idle");
  const [result, setResult] = React.useState<UploadResult | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const inputRef = React.useRef<HTMLInputElement>(null);

  async function handleFile(file: File) {
    setState("uploading");
    setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      if (folder) fd.append("folder", folder);

      // Auth-aware: only `/uploads` requires Bearer; /uploads/public is open.
      const headers: Record<string, string> = {};
      if (endpoint === "/uploads") {
        const token = typeof window !== "undefined" ? localStorage.getItem("quata_token") : null;
        if (token) headers.Authorization = `Bearer ${token}`;
      }

      const res = await fetch(`${apiUrl}${endpoint}`, {
        method: "POST",
        body: fd,
        headers,
      });
      if (!res.ok) {
        let detail = res.statusText;
        try { detail = (await res.json()).detail ?? detail; } catch {}
        throw new Error(detail);
      }
      const data: UploadResult = await res.json();
      setResult(data);
      setState("done");
      onUploaded?.(data);
    } catch (err) {
      setState("error");
      setError(err instanceof Error ? err.message : "Upload failed");
    }
  }

  function clear() {
    setState("idle");
    setResult(null);
    setError(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  return (
    <div className={cn("grid gap-2", className)}>
      <label
        className={cn(
          "flex items-center justify-between gap-3 rounded-xl border border-dashed border-border bg-surface-soft p-3.5 cursor-pointer transition hover:border-primary/40",
          state === "done" && "border-emerald-300 bg-emerald-50",
          state === "error" && "border-rose-300 bg-rose-50"
        )}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          className="sr-only"
          onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
        />
        <div className="flex items-center gap-3 min-w-0">
          <div className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-brand-soft text-primary">
            {state === "uploading" ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : state === "done" ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-700" />
            ) : (
              <FileUp className="h-4 w-4" />
            )}
          </div>
          <div className="min-w-0">
            {state === "done" && result ? (
              <>
                <div className="text-sm font-medium truncate">{result.filename}</div>
                <div className="text-xs text-muted-foreground">
                  {(result.size / 1024).toFixed(1)} KB · uploaded
                </div>
              </>
            ) : state === "error" ? (
              <div className="text-sm text-rose-900">Upload failed — {error}</div>
            ) : (
              <>
                <div className="text-sm font-medium">Click to upload</div>
                <div className="text-xs text-muted-foreground">{hint ?? "Up to 25 MB"}</div>
              </>
            )}
          </div>
        </div>
        {state === "done" && (
          <button
            type="button"
            aria-label="Clear"
            onClick={(e) => {
              e.preventDefault();
              clear();
            }}
            className="text-muted-foreground hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </label>
      {/* Hidden field carrying the URL for parent form submission */}
      <input type="hidden" name={name} value={result?.url ?? ""} />
    </div>
  );
}
