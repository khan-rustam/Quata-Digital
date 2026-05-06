"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  CheckCircle2,
  CircleDot,
  Eye,
  EyeOff,
  ExternalLink,
  History,
  Loader2,
  Plus,
  Save,
  Trash2,
  GripVertical,
} from "lucide-react";

import { PageShell } from "@/components/admin/page-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { useApi, useApiAction } from "@/lib/use-api";
import { useToast } from "@/components/ui/toast";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  SlideOver,
  SlideOverContent,
} from "@/components/admin/slide-over";
import {
  SECTION_FORMS,
  NEW_SECTION_DEFAULTS,
} from "@/components/admin/cms-section-forms";
import type { Section } from "@/lib/page-content";

type PageDetail = {
  slug: string;
  title: string;
  page_type: string;
  description: string | null;
  is_published: boolean;
  published_at: string | null;
  sections: Section[];
  updated_at: string;
  created_at: string;
  updated_by: string | null;
};

type SectionTypeMeta = {
  type: Section["type"];
  label: string;
  description: string;
};

type Catalogue = {
  types: SectionTypeMeta[];
  allowed_per_page_type: Record<string, string[]>;
};

const TYPE_LABELS: Record<Section["type"], string> = {
  hero: "Hero",
  feature_grid: "Feature grid",
  icon_badge: "Icon badge",
  big_quote: "Big quote",
  faq: "FAQ",
  stat_strip: "Stat strip",
  testimonials: "Testimonials",
  timeline: "Timeline",
  process_steps: "Process steps",
  logo_cloud: "Logo cloud",
  cta: "Call-to-action",
  newsletter_cta: "Newsletter signup",
  rich_text: "Rich text",
  image_text: "Image + text",
};

export default function PageEditor() {
  const params = useParams();
  const slug = decodeURIComponent(
    Array.isArray(params.slug) ? params.slug.join("/") : (params.slug as string),
  );
  return (
    <PageShell
      title="Editing page"
      description={`/${slug}`}
      requirePermission="content:manage"
    >
      <PageEditorBody slug={slug} />
    </PageShell>
  );
}

function PageEditorBody({ slug }: { slug: string }) {
  const action = useApiAction();
  const toast = useToast();
  const { data, loading, error, refresh } = useApi<PageDetail>(`/admin/cms/pages/${encodeURIComponent(slug)}`);
  const { data: catalogue } = useApi<Catalogue>("/admin/cms/section-catalogue");

  const [draft, setDraft] = React.useState<PageDetail | null>(null);
  const [editingIndex, setEditingIndex] = React.useState<number | null>(null);
  const [picker, setPicker] = React.useState(false);
  const [submitting, setSubmitting] = React.useState(false);
  const [confirmRemove, setConfirmRemove] = React.useState<number | null>(null);
  const [historyOpen, setHistoryOpen] = React.useState(false);

  // Hydrate draft once data arrives, and on refresh.
  React.useEffect(() => {
    if (data) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- copying server data into editable working draft.
      setDraft(data);
    }
  }, [data]);

  if (loading || !draft) {
    return <div className="text-sm text-muted-foreground">Loading…</div>;
  }
  if (error) {
    return (
      <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-rose-900">
        Couldn&apos;t load this page.
      </div>
    );
  }

  // Stable non-null reference. TS narrowing doesn't survive function-decl
  // closures, so binding to a const lets the helpers below see PageDetail
  // (not PageDetail | null). Same value at any callsite within this render.
  const d: PageDetail = draft;

  const dirty =
    d.title !== data?.title ||
    (d.description ?? "") !== (data?.description ?? "") ||
    JSON.stringify(d.sections) !== JSON.stringify(data?.sections);

  const allowedTypes = new Set(
    catalogue?.allowed_per_page_type[d.page_type] ?? [],
  );

  function setSections(sections: Section[]) {
    setDraft((d) => (d ? { ...d, sections } : d));
  }

  function moveSection(from: number, dir: -1 | 1) {
    const to = from + dir;
    if (to < 0 || to >= d.sections.length) return;
    const copy = [...d.sections];
    [copy[from], copy[to]] = [copy[to], copy[from]];
    setSections(copy);
  }

  function toggleVisible(i: number) {
    const copy = [...d.sections];
    copy[i] = { ...copy[i], visible: !(copy[i].visible !== false) };
    setSections(copy);
  }

  function removeSection(i: number) {
    setSections(d.sections.filter((_, idx) => idx !== i));
    setConfirmRemove(null);
  }

  function addSection(type: Section["type"]) {
    const next = NEW_SECTION_DEFAULTS[type]();
    setSections([...d.sections, next]);
    setEditingIndex(d.sections.length);
    setPicker(false);
  }

  function updateSection(i: number, next: Section) {
    const copy = [...d.sections];
    copy[i] = next;
    setSections(copy);
  }

  async function save() {
    setSubmitting(true);
    try {
      const updated = await action<PageDetail>(`/admin/cms/pages/${encodeURIComponent(slug)}`, {
        method: "PUT",
        body: JSON.stringify({
          title: d.title,
          description: d.description,
          sections: d.sections,
        }),
      });
      toast.success("Saved", "Changes are live in ~10 seconds on the public site.");
      // refresh from server (gets server-stamped section ids etc.)
      setDraft(updated);
      refresh();
    } catch (err) {
      toast.error("Couldn't save", err instanceof Error ? err.message : "Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  async function publish(next: boolean) {
    try {
      await action(`/admin/cms/pages/${encodeURIComponent(slug)}/${next ? "publish" : "unpublish"}`, {
        method: "POST",
      });
      toast.success(next ? "Published" : "Unpublished");
      refresh();
    } catch (err) {
      toast.error("Couldn't update", err instanceof Error ? err.message : "Try again.");
    }
  }

  return (
    <div className="grid gap-6">
      {/* Header strip */}
      <div className="rounded-2xl border border-border bg-card p-5 ring-soft flex flex-wrap items-center gap-3">
        <Button variant="outline" size="sm" asChild>
          <Link href="/admin/cms/pages">
            <ArrowLeft className="h-3.5 w-3.5" /> All pages
          </Link>
        </Button>
        <div className="hidden sm:flex items-center gap-2 text-xs text-muted-foreground font-mono">
          /{slug}
        </div>
        <div className="ml-auto flex items-center gap-2">
          {d.is_published ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 text-emerald-800 px-2 py-1 text-xs font-medium">
              <CheckCircle2 className="h-3 w-3" /> Published
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 text-amber-800 px-2 py-1 text-xs font-medium">
              <CircleDot className="h-3 w-3" /> Draft
            </span>
          )}
          <Button asChild variant="outline" size="sm">
            <a href={`/${slug === "home" ? "" : slug}`} target="_blank" rel="noreferrer">
              <ExternalLink className="h-3.5 w-3.5" /> View
            </a>
          </Button>
          <Button variant="outline" size="sm" onClick={() => setHistoryOpen(true)}>
            <History className="h-3.5 w-3.5" /> History
          </Button>
          {d.is_published ? (
            <Button variant="outline" size="sm" onClick={() => publish(false)}>
              Unpublish
            </Button>
          ) : (
            <Button size="sm" onClick={() => publish(true)} disabled={dirty}>
              Publish
            </Button>
          )}
          <Button onClick={save} disabled={!dirty || submitting}>
            {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            {dirty ? "Save changes" : "Saved"}
          </Button>
        </div>
      </div>

      {/* Page metadata */}
      <div className="rounded-2xl border border-border bg-card p-6 ring-soft grid gap-4 max-w-3xl">
        <div className="grid gap-1.5">
          <Label>Page title</Label>
          <Input
            value={d.title}
            onChange={(e) =>
              setDraft((d) => (d ? { ...d, title: e.target.value } : d))
            }
            placeholder="Page title"
          />
          <div className="text-xs text-muted-foreground">
            Used in admin lists and as the default browser tab title for this page.
          </div>
        </div>
        <div className="grid gap-1.5">
          <Label>Description (admin only)</Label>
          <Textarea
            rows={2}
            value={d.description ?? ""}
            onChange={(e) =>
              setDraft((d) => (d ? { ...d, description: e.target.value || null } : d))
            }
            placeholder="A one-line note for the admin team."
          />
        </div>
      </div>

      {/* Sections */}
      <div className="grid gap-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Sections ({d.sections.length})
          </h3>
          <Button onClick={() => setPicker(true)} disabled={!catalogue}>
            <Plus className="h-3.5 w-3.5" /> Add section
          </Button>
        </div>

        {d.sections.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border bg-surface-soft p-10 text-center">
            <div className="text-sm text-muted-foreground">
              No sections yet. Click <strong>Add section</strong> to start composing this page.
            </div>
          </div>
        ) : (
          <ol className="grid gap-2">
            {d.sections.map((s, i) => (
              <li
                key={s.id}
                className="rounded-2xl border border-border bg-card p-4 ring-soft flex flex-wrap items-center gap-3"
              >
                <div className="flex items-center gap-2 text-muted-foreground">
                  <GripVertical className="h-4 w-4" />
                  <span className="font-mono text-xs">#{i + 1}</span>
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-semibold">
                    {TYPE_LABELS[s.type]}
                  </div>
                  <div className="text-xs text-muted-foreground truncate">
                    {summariseSection(s)}
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={i === 0}
                    onClick={() => moveSection(i, -1)}
                    aria-label="Move up"
                  >
                    ↑
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={i === d.sections.length - 1}
                    onClick={() => moveSection(i, 1)}
                    aria-label="Move down"
                  >
                    ↓
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => toggleVisible(i)}
                    aria-label={s.visible !== false ? "Hide section" : "Show section"}
                  >
                    {s.visible !== false ? <Eye className="h-3.5 w-3.5" /> : <EyeOff className="h-3.5 w-3.5" />}
                  </Button>
                  <Button size="sm" onClick={() => setEditingIndex(i)}>
                    Edit
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setConfirmRemove(i)}
                    aria-label="Remove section"
                  >
                    <Trash2 className="h-3.5 w-3.5 text-rose-700" />
                  </Button>
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>

      {/* Section picker slide-over */}
      <SlideOver open={picker} onOpenChange={setPicker}>
        <SlideOverContent
          title="Add a section"
          description={`Choose a section type for ${d.title}.`}
          size="md"
        >
          <SectionPicker
            allowedTypes={allowedTypes}
            onPick={(t) => addSection(t)}
            catalogue={catalogue}
            pageType={d.page_type}
          />
        </SlideOverContent>
      </SlideOver>

      {/* Section editor slide-over */}
      <SlideOver
        open={editingIndex !== null}
        onOpenChange={(o) => !o && setEditingIndex(null)}
      >
        <SlideOverContent
          title={editingIndex !== null ? `Edit ${TYPE_LABELS[d.sections[editingIndex].type]}` : ""}
          description="Changes apply to this section only. Click Done when finished, then Save changes at the top to commit."
          size="xl"
        >
          {editingIndex !== null && (
            <SectionEditor
              section={d.sections[editingIndex]}
              onChange={(next) => updateSection(editingIndex, next)}
              onDone={() => setEditingIndex(null)}
            />
          )}
        </SlideOverContent>
      </SlideOver>

      {/* History slide-over */}
      <SlideOver open={historyOpen} onOpenChange={setHistoryOpen}>
        <SlideOverContent
          title="Version history"
          description={`Last ${10} saves of this page. Click Restore to bring a version back — your current state is snapshotted first so you can revert the revert.`}
          size="md"
        >
          <HistoryPanel
            slug={slug}
            open={historyOpen}
            onRestored={() => {
              setHistoryOpen(false);
              refresh();
            }}
          />
        </SlideOverContent>
      </SlideOver>

      {/* Confirm remove */}
      <ConfirmDialog
        open={confirmRemove !== null}
        onOpenChange={(o) => !o && setConfirmRemove(null)}
        title="Remove this section?"
        description="It'll be gone after you click Save changes. Until then you can undo by reloading."
        confirmLabel="Remove"
        destructive
        onConfirm={() => {
          if (confirmRemove !== null) removeSection(confirmRemove);
        }}
      />
    </div>
  );
}

function SectionPicker({
  allowedTypes,
  onPick,
  catalogue,
  pageType,
}: {
  allowedTypes: Set<string>;
  onPick: (type: Section["type"]) => void;
  catalogue: Catalogue | null;
  pageType: string;
}) {
  if (!catalogue) {
    return <div className="text-sm text-muted-foreground">Loading types…</div>;
  }
  return (
    <div className="grid gap-2">
      <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
        {allowedTypes.size === catalogue.types.length
          ? "Every section type is available on this page."
          : `Only ${allowedTypes.size} of ${catalogue.types.length} section types are allowed on a ${pageType} page (others are filtered out).`}
      </div>
      {catalogue.types
        .filter((t) => allowedTypes.has(t.type))
        .map((t) => (
          <button
            key={t.type}
            type="button"
            onClick={() => onPick(t.type)}
            className="text-left rounded-xl border border-border bg-card p-4 ring-soft hover:ring-elevated transition"
          >
            <div className="text-sm font-semibold">{t.label}</div>
            <div className="mt-1 text-xs text-muted-foreground">{t.description}</div>
          </button>
        ))}
    </div>
  );
}

function SectionEditor({
  section,
  onChange,
  onDone,
}: {
  section: Section;
  onChange: (next: Section) => void;
  onDone: () => void;
}) {
  const Form = SECTION_FORMS[section.type];
  return (
    <div className="grid gap-5">
      <Form section={section} onChange={onChange} />
      <div className="flex justify-end pt-3 border-t border-border">
        <Button onClick={onDone}>Done</Button>
      </div>
    </div>
  );
}

type VersionRow = {
  id: number;
  page_slug: string;
  title: string;
  section_count: number;
  saved_by: string | null;
  created_at: string | null;
};

function HistoryPanel({
  slug,
  open,
  onRestored,
}: {
  slug: string;
  open: boolean;
  onRestored: () => void;
}) {
  const action = useApiAction();
  const toast = useToast();
  const [versions, setVersions] = React.useState<VersionRow[] | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [restoring, setRestoring] = React.useState<number | null>(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const data = await action<VersionRow[]>(
        `/admin/cms/page-versions/${encodeURIComponent(slug)}`,
      );
      setVersions(data);
    } catch (err) {
      toast.error("Couldn't load history", err instanceof Error ? err.message : "Try again.");
    } finally {
      setLoading(false);
    }
  }, [action, slug, toast]);

  React.useEffect(() => {
    if (open) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional: refetch history when the slide-over opens.
      load();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  async function restore(id: number) {
    setRestoring(id);
    try {
      await action(
        `/admin/cms/page-versions/${encodeURIComponent(slug)}/revert/${id}`,
        { method: "POST" },
      );
      toast.success("Restored", "The page now shows the snapshotted version. Save again or publish if you're happy.");
      onRestored();
    } catch (err) {
      toast.error("Couldn't restore", err instanceof Error ? err.message : "Try again.");
    } finally {
      setRestoring(null);
    }
  }

  if (loading || versions === null) {
    return <div className="text-sm text-muted-foreground">Loading history…</div>;
  }
  if (versions.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border bg-surface-soft p-8 text-center text-sm text-muted-foreground">
        No history yet. The first save will start the version log.
      </div>
    );
  }
  return (
    <ol className="grid gap-2">
      {versions.map((v, i) => (
        <li
          key={v.id}
          className="rounded-xl border border-border bg-card p-4 ring-soft"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="text-xs uppercase tracking-wider text-muted-foreground">
                {i === 0 ? "Most recent" : `${i + 1} saves ago`}
              </div>
              <div className="mt-0.5 text-sm font-medium truncate">{v.title}</div>
              <div className="mt-0.5 text-xs text-muted-foreground">
                {v.section_count} section{v.section_count === 1 ? "" : "s"}
                {v.saved_by ? ` · by ${v.saved_by}` : ""}
                {v.created_at ? ` · ${new Date(v.created_at).toLocaleString()}` : ""}
              </div>
            </div>
            <Button
              size="sm"
              variant={i === 0 ? "outline" : undefined}
              onClick={() => restore(v.id)}
              disabled={restoring !== null}
            >
              {restoring === v.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
              {i === 0 ? "Restore (no-op)" : "Restore"}
            </Button>
          </div>
        </li>
      ))}
    </ol>
  );
}

function summariseSection(s: Section): string {
  switch (s.type) {
    case "hero":
      return s.title || "Hero (no title)";
    case "feature_grid":
      return s.title || `${s.items.length} feature${s.items.length === 1 ? "" : "s"}`;
    case "icon_badge":
      return s.title || "Icon badge";
    case "big_quote":
      return s.quote ? `"${s.quote.slice(0, 70)}${s.quote.length > 70 ? "…" : ""}"` : "Big quote";
    case "faq":
      return `${s.items.length} question${s.items.length === 1 ? "" : "s"}`;
    case "stat_strip":
      return `${s.items.length} stat${s.items.length === 1 ? "" : "s"}`;
    case "testimonials":
      return `${s.items.length} testimonial${s.items.length === 1 ? "" : "s"}`;
    case "timeline":
      return `${s.items.length} milestone${s.items.length === 1 ? "" : "s"}`;
    case "process_steps":
      return `${s.items.length} step${s.items.length === 1 ? "" : "s"}`;
    case "logo_cloud":
      return `${s.items.length} logo${s.items.length === 1 ? "" : "s"}`;
    case "cta":
      return s.title || "Call-to-action";
    case "newsletter_cta":
      return s.title ?? "Newsletter signup";
    case "rich_text":
      return s.body.slice(0, 80) + (s.body.length > 80 ? "…" : "");
    case "image_text":
      return s.title ?? s.body.slice(0, 60);
    default:
      return "";
  }
}
