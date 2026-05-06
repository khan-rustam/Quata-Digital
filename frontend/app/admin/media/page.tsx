"use client";

import * as React from "react";
import {
  Copy,
  Image as ImageIcon,
  FileText,
  Loader2,
  Plus,
  Search,
  Tag as TagIcon,
  Trash2,
  Upload,
} from "lucide-react";

import { PageShell } from "@/components/admin/page-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  SlideOver,
  SlideOverContent,
} from "@/components/admin/slide-over";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useApi, useApiAction } from "@/lib/use-api";
import { useToast } from "@/components/ui/toast";
import { apiUrl } from "@/lib/api";
import { formatDate } from "@/lib/utils";

type MediaItem = {
  id: number;
  url: string;
  filename: string;
  original_filename: string | null;
  content_type: string;
  size: number;
  folder: string;
  width: number | null;
  height: number | null;
  optimized_url: string | null;
  optimized_size: number | null;
  alt_text: string | null;
  tags: string[];
  used_on: string[];
  uploaded_by: string | null;
  created_at: string;
};

type ListResponse = {
  items: MediaItem[];
  total: number;
  limit: number;
  offset: number;
  folders: string[];
};

const TYPE_FILTERS: { label: string; prefix: string | null }[] = [
  { label: "All", prefix: null },
  { label: "Images", prefix: "image/" },
  { label: "Documents", prefix: "application/" },
];

export default function MediaLibraryPage() {
  return (
    <PageShell
      title="Media library"
      description="Every image and file uploaded through the admin. Reuse across pages without re-uploading."
      requirePermission="content:manage"
    >
      <MediaLibrary />
    </PageShell>
  );
}

function MediaLibrary() {
  const action = useApiAction();
  const toast = useToast();
  const [query, setQuery] = React.useState("");
  const [folder, setFolder] = React.useState<string | null>(null);
  const [typePrefix, setTypePrefix] = React.useState<string | null>(null);

  const path = React.useMemo(() => {
    const p = new URLSearchParams();
    if (query.trim()) p.set("q", query.trim());
    if (folder) p.set("folder", folder);
    if (typePrefix) p.set("content_type_prefix", typePrefix);
    p.set("limit", "120");
    return `/admin/media?${p.toString()}`;
  }, [query, folder, typePrefix]);

  const { data, loading, refresh } = useApi<ListResponse>(path);
  const [editing, setEditing] = React.useState<MediaItem | null>(null);
  const [deleting, setDeleting] = React.useState<MediaItem | null>(null);
  const [uploading, setUploading] = React.useState(false);
  const fileRef = React.useRef<HTMLInputElement>(null);

  async function uploadFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    setUploading(true);
    let okCount = 0;
    let failCount = 0;
    for (const file of Array.from(files)) {
      try {
        const fd = new FormData();
        fd.append("file", file);
        fd.append("folder", "library");
        const headers: Record<string, string> = {};
        const token = typeof window !== "undefined" ? localStorage.getItem("quata_token") : null;
        if (token) headers.Authorization = `Bearer ${token}`;
        const res = await fetch(`${apiUrl}/uploads`, { method: "POST", body: fd, headers });
        if (!res.ok) throw new Error(await res.text());
        okCount++;
      } catch {
        failCount++;
      }
    }
    setUploading(false);
    if (okCount > 0) {
      toast.success(
        `Uploaded ${okCount}`,
        failCount > 0 ? `${failCount} failed.` : "All files added to the library.",
      );
      refresh();
    } else if (failCount > 0) {
      toast.error("Upload failed", `${failCount} file(s) couldn't upload. Try again.`);
    }
    if (fileRef.current) fileRef.current.value = "";
  }

  async function saveMeta(id: number, alt_text: string, tags: string[]) {
    try {
      await action(`/admin/media/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ alt_text, tags }),
      });
      toast.success("Saved");
      setEditing(null);
      refresh();
    } catch (err) {
      toast.error("Couldn't save", err instanceof Error ? err.message : "Try again.");
    }
  }

  async function destroy(id: number, force = false) {
    try {
      await action(`/admin/media/${id}${force ? "?force=true" : ""}`, { method: "DELETE" });
      toast.success("Removed", "The file is hidden from the library; the underlying file is preserved.");
      setDeleting(null);
      refresh();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Try again.";
      // Backend returns 409 with `used_on` list when the asset is referenced.
      if (msg.includes("409") && msg.includes("asset_in_use")) {
        // The toast carries enough; the ConfirmDialog also exposes Force.
        toast.error("Still in use", "This asset is referenced by one or more pages. Use the dialog's Force button to remove anyway.");
        return;
      }
      toast.error("Couldn't remove", msg);
    }
  }

  return (
    <div className="grid gap-4">
      {/* Toolbar */}
      <div className="grid gap-3 lg:grid-cols-[1fr_auto] items-center">
        <div className="relative">
          <Search className="absolute inset-y-0 left-3 h-4 w-4 my-auto text-muted-foreground" />
          <Input
            placeholder="Search filename, alt text or tags…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="pl-9"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          <input
            ref={fileRef}
            type="file"
            multiple
            accept="image/*,application/*,text/*"
            className="sr-only"
            onChange={(e) => uploadFiles(e.target.files)}
          />
          <Button onClick={() => fileRef.current?.click()} disabled={uploading}>
            {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
            Upload
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs">
        {TYPE_FILTERS.map((t) => (
          <FilterChip
            key={t.label}
            active={typePrefix === t.prefix}
            onClick={() => setTypePrefix(t.prefix)}
          >
            {t.label}
          </FilterChip>
        ))}
        <span className="mx-2 h-4 w-px bg-border" aria-hidden />
        <FilterChip active={folder === null} onClick={() => setFolder(null)}>
          All folders
        </FilterChip>
        {(data?.folders ?? []).map((f) => (
          <FilterChip key={f} active={folder === f} onClick={() => setFolder(f)}>
            {f}
          </FilterChip>
        ))}
      </div>

      {/* Grid */}
      {loading ? (
        <div className="text-sm text-muted-foreground">Loading…</div>
      ) : !data || data.items.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border bg-surface-soft p-12 text-center">
          <ImageIcon className="h-6 w-6 mx-auto mb-3 text-muted-foreground" />
          <div className="text-sm font-medium">No files yet</div>
          <div className="mt-1 text-xs text-muted-foreground">
            Click <strong>Upload</strong> above, or upload images directly inside any CMS section editor —
            they all land here.
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          {data.items.map((m) => (
            <MediaTile
              key={m.id}
              item={m}
              onClick={() => setEditing(m)}
              onCopy={async () => {
                await navigator.clipboard.writeText(m.url);
                toast.success("URL copied");
              }}
            />
          ))}
        </div>
      )}

      {data && (
        <div className="text-xs text-muted-foreground">
          {data.items.length} of {data.total} file{data.total === 1 ? "" : "s"}.
        </div>
      )}

      {/* Edit slide-over */}
      <SlideOver
        open={editing !== null}
        onOpenChange={(o) => !o && setEditing(null)}
      >
        <SlideOverContent
          title={editing?.original_filename ?? editing?.filename ?? ""}
          description="Edit metadata. The file URL is fixed once uploaded."
          size="md"
        >
          {editing && (
            <MediaEditor
              item={editing}
              onSave={(alt, tags) => saveMeta(editing.id, alt, tags)}
              onDelete={() => {
                setDeleting(editing);
                setEditing(null);
              }}
            />
          )}
        </SlideOverContent>
      </SlideOver>

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(o) => !o && setDeleting(null)}
        title={`Remove "${deleting?.original_filename ?? deleting?.filename ?? "file"}" from library?`}
        description={
          deleting && deleting.used_on && deleting.used_on.length > 0
            ? `In use on: ${deleting.used_on.map((s) => `/${s}`).join(", ")}. The file on disk stays — pages keep rendering — but the asset is hidden from the library.`
            : "The file on disk is preserved — pages still using the URL keep rendering. You can't undo this from the UI; ask engineering to restore."
        }
        confirmLabel={
          deleting && deleting.used_on && deleting.used_on.length > 0
            ? "Force remove"
            : "Remove"
        }
        destructive
        onConfirm={() => {
          if (!deleting) return;
          const inUse = (deleting.used_on || []).length > 0;
          destroy(deleting.id, inUse);
        }}
      />
    </div>
  );
}

function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-1 rounded-full border px-3 py-1 transition ${
        active
          ? "border-primary bg-brand-soft text-primary"
          : "border-border bg-surface text-muted-foreground hover:text-foreground"
      }`}
    >
      {children}
    </button>
  );
}

function MediaTile({
  item,
  onClick,
  onCopy,
}: {
  item: MediaItem;
  onClick: () => void;
  onCopy: () => void;
}) {
  const isImage = item.content_type.startsWith("image/");
  return (
    <div className="group rounded-xl border border-border bg-card overflow-hidden ring-soft hover:ring-elevated transition">
      <button
        type="button"
        onClick={onClick}
        className="block relative w-full aspect-square bg-secondary"
        aria-label={`Edit ${item.original_filename ?? item.filename}`}
      >
        {isImage ? (
          // eslint-disable-next-line @next/next/no-img-element -- thumbnail grid; opt is overkill.
          <img
            src={item.url}
            alt={item.alt_text ?? item.original_filename ?? ""}
            className="absolute inset-0 h-full w-full object-cover"
            loading="lazy"
          />
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-muted-foreground">
            <FileText className="h-8 w-8" />
            <span className="mt-2 text-[10px] font-mono uppercase">
              {item.content_type.split("/")[1] ?? item.content_type}
            </span>
          </div>
        )}
      </button>
      <div className="p-2.5">
        <div className="text-xs font-medium truncate" title={item.original_filename ?? item.filename}>
          {item.original_filename ?? item.filename}
        </div>
        <div className="mt-0.5 flex items-center justify-between text-[10px] text-muted-foreground">
          <span>
            {item.width && item.height ? `${item.width}×${item.height} · ` : ""}
            {formatBytes(item.size)}
          </span>
          <button
            type="button"
            onClick={onCopy}
            className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-muted-foreground hover:bg-secondary hover:text-foreground"
            title="Copy URL"
          >
            <Copy className="h-3 w-3" /> URL
          </button>
        </div>
        {item.optimized_url && item.optimized_size && (
          <div className="mt-0.5 text-[10px] text-emerald-700">
            WebP {formatBytes(item.optimized_size)} ({Math.round((1 - item.optimized_size / item.size) * 100)}% smaller)
          </div>
        )}
        {item.tags && item.tags.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1">
            {item.tags.slice(0, 2).map((t) => (
              <span key={t} className="rounded-full bg-secondary px-1.5 py-0.5 text-[10px] text-muted-foreground">
                {t}
              </span>
            ))}
            {item.tags.length > 2 && (
              <span className="text-[10px] text-muted-foreground">+{item.tags.length - 2}</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function MediaEditor({
  item,
  onSave,
  onDelete,
}: {
  item: MediaItem;
  onSave: (alt: string, tags: string[]) => Promise<void> | void;
  onDelete: () => void;
}) {
  const [alt, setAlt] = React.useState(item.alt_text ?? "");
  const [tagsRaw, setTagsRaw] = React.useState((item.tags ?? []).join(", "));
  const [submitting, setSubmitting] = React.useState(false);
  const isImage = item.content_type.startsWith("image/");
  return (
    <div className="grid gap-4">
      {isImage ? (
        // eslint-disable-next-line @next/next/no-img-element -- preview only.
        <img
          src={item.url}
          alt={alt}
          className="w-full rounded-xl border border-border bg-secondary object-contain max-h-75"
        />
      ) : (
        <div className="flex items-center gap-3 rounded-xl border border-border bg-surface p-4">
          <FileText className="h-6 w-6 text-muted-foreground" />
          <div className="text-sm">{item.content_type}</div>
        </div>
      )}

      <div className="grid gap-1.5">
        <Label>File URL</Label>
        <div className="flex items-center gap-2">
          <Input value={item.url} readOnly className="font-mono text-xs" />
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => navigator.clipboard.writeText(item.url)}
          >
            <Copy className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      <div className="grid gap-1.5">
        <Label htmlFor="alt-text">Alt text</Label>
        <Textarea
          id="alt-text"
          rows={2}
          value={alt}
          onChange={(e) => setAlt(e.target.value)}
          placeholder="Describe the image for screen readers and SEO."
          maxLength={255}
        />
      </div>

      <div className="grid gap-1.5">
        <Label htmlFor="tags">
          <span className="inline-flex items-center gap-1">
            <TagIcon className="h-3 w-3" /> Tags
          </span>
        </Label>
        <Input
          id="tags"
          value={tagsRaw}
          onChange={(e) => setTagsRaw(e.target.value)}
          placeholder="comma, separated, tags"
        />
        <div className="text-xs text-muted-foreground">
          Tags help you search the library. Lowercase, max 40 chars each.
        </div>
      </div>

      <div className="grid gap-1 text-xs text-muted-foreground border-t border-border pt-4">
        <div>
          <span className="text-foreground">Folder:</span> <code className="font-mono">{item.folder}</code>
        </div>
        <div>
          <span className="text-foreground">Size:</span> {formatBytes(item.size)}
          {item.width && item.height ? ` · ${item.width}×${item.height}` : ""}
        </div>
        {item.optimized_url && item.optimized_size && (
          <div className="text-emerald-700">
            <span className="text-foreground">WebP:</span> {formatBytes(item.optimized_size)}{" "}
            ({Math.round((1 - item.optimized_size / item.size) * 100)}% smaller, served by default)
          </div>
        )}
        <div>
          <span className="text-foreground">Type:</span> <code className="font-mono">{item.content_type}</code>
        </div>
        <div>
          <span className="text-foreground">Uploaded:</span>{" "}
          {formatDate(item.created_at)}
          {item.uploaded_by ? ` · ${item.uploaded_by}` : ""}
        </div>
        {item.used_on && item.used_on.length > 0 && (
          <div>
            <span className="text-foreground">Used on:</span>{" "}
            {item.used_on.map((slug, i) => (
              <span key={slug}>
                <code className="font-mono">/{slug}</code>
                {i < item.used_on.length - 1 ? ", " : ""}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="flex justify-between pt-3 border-t border-border">
        <Button
          variant="outline"
          onClick={onDelete}
          className="text-rose-700 hover:bg-rose-50"
        >
          <Trash2 className="h-3.5 w-3.5" /> Remove
        </Button>
        <Button
          onClick={async () => {
            setSubmitting(true);
            try {
              const tags = tagsRaw
                .split(",")
                .map((s) => s.trim())
                .filter(Boolean);
              await onSave(alt, tags);
            } finally {
              setSubmitting(false);
            }
          }}
          disabled={submitting}
        >
          {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
          Save
        </Button>
      </div>
    </div>
  );
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}
