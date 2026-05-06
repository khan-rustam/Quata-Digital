"use client";

/**
 * "Pick from library" — a slide-over wrapping the media library so any CMS
 * image field can let the boss reuse a previously-uploaded asset rather
 * than re-uploading. Picks the URL by id and returns it via `onPick`.
 */
import * as React from "react";
import { FileText, Image as ImageIcon, Loader2, Search } from "lucide-react";

import {
  SlideOver,
  SlideOverContent,
  SlideOverTrigger,
} from "@/components/admin/slide-over";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useApi } from "@/lib/use-api";

type MediaItem = {
  id: number;
  url: string;
  filename: string;
  original_filename: string | null;
  content_type: string;
  size: number;
  alt_text: string | null;
};

type ListResponse = {
  items: MediaItem[];
  total: number;
};

export function MediaPickerButton({
  onPick,
  imagesOnly = true,
  triggerLabel = "Pick from library",
}: {
  onPick: (url: string, alt?: string | null) => void;
  imagesOnly?: boolean;
  triggerLabel?: string;
}) {
  const [open, setOpen] = React.useState(false);
  return (
    <SlideOver open={open} onOpenChange={setOpen}>
      <SlideOverTrigger asChild>
        <Button type="button" variant="outline" size="sm">
          <ImageIcon className="h-3.5 w-3.5" /> {triggerLabel}
        </Button>
      </SlideOverTrigger>
      <SlideOverContent
        title="Pick from library"
        description="Reuse an asset already in the library. Click any tile to select it."
        size="lg"
      >
        <PickerBody
          imagesOnly={imagesOnly}
          onPick={(url, alt) => {
            onPick(url, alt);
            setOpen(false);
          }}
        />
      </SlideOverContent>
    </SlideOver>
  );
}

function PickerBody({
  imagesOnly,
  onPick,
}: {
  imagesOnly: boolean;
  onPick: (url: string, alt?: string | null) => void;
}) {
  const [query, setQuery] = React.useState("");
  const path = React.useMemo(() => {
    const p = new URLSearchParams();
    if (query.trim()) p.set("q", query.trim());
    if (imagesOnly) p.set("content_type_prefix", "image/");
    p.set("limit", "60");
    return `/admin/media?${p.toString()}`;
  }, [query, imagesOnly]);
  const { data, loading } = useApi<ListResponse>(path);

  return (
    <div className="grid gap-3">
      <div className="relative">
        <Search className="absolute inset-y-0 left-3 h-4 w-4 my-auto text-muted-foreground" />
        <Input
          autoFocus
          placeholder="Search by filename, alt text or tag…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="pl-9"
        />
      </div>
      {loading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading library…
        </div>
      ) : !data || data.items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border bg-surface-soft p-8 text-center text-sm text-muted-foreground">
          No matching files. Upload via the toolbar to add to the library.
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {data.items.map((m) => (
            <button
              key={m.id}
              type="button"
              onClick={() => onPick(m.url, m.alt_text)}
              className="group rounded-xl border border-border bg-card overflow-hidden ring-soft hover:ring-elevated transition text-left"
            >
              <div className="relative w-full aspect-square bg-secondary">
                {m.content_type.startsWith("image/") ? (
                  // eslint-disable-next-line @next/next/no-img-element -- thumbnail grid; opt is overkill.
                  <img
                    src={m.url}
                    alt={m.alt_text ?? m.original_filename ?? ""}
                    className="absolute inset-0 h-full w-full object-cover"
                    loading="lazy"
                  />
                ) : (
                  <div className="absolute inset-0 flex items-center justify-center text-muted-foreground">
                    <FileText className="h-6 w-6" />
                  </div>
                )}
              </div>
              <div className="p-2">
                <div className="text-[11px] font-medium truncate">
                  {m.original_filename ?? m.filename}
                </div>
                {m.alt_text && (
                  <div className="text-[10px] text-muted-foreground truncate">{m.alt_text}</div>
                )}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
