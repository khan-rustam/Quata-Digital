"use client";

/**
 * Per-section admin forms. The page editor opens a slide-over with one of
 * these forms based on the section's `type`. Each form receives the section
 * object and an `onChange` callback; `onSave` is invoked by the slide-over
 * after Save is clicked.
 *
 * Adding a new section type:
 *   1. Add the renderer in components/site/sections/section-renderer.tsx.
 *   2. Add a form below.
 *   3. Add the type to `SECTION_FORMS` at the bottom.
 */

import * as React from "react";
import { Plus, Trash2, Image as ImageIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select } from "@/components/ui/select";
import { FileUpload, type UploadResult } from "@/components/forms/file-upload";
import { MediaPickerButton } from "@/components/admin/media-picker";
import type {
  Section,
  HeroSection,
  FeatureGridSection,
  FeatureItem,
  IconBadgeSection,
  BigQuoteSection,
  FaqSection,
  FaqItem,
  StatStripSection,
  StatItem,
  TestimonialsSection,
  TestimonialItem,
  TimelineSection,
  TimelineItem,
  ProcessStepsSection,
  ProcessStepItem,
  LogoCloudSection,
  LogoItem,
  CtaSection,
  NewsletterCtaSection,
  RichTextSection,
  ImageTextSection,
} from "@/lib/page-content";

type SectionFormProps<T extends Section> = {
  section: T;
  onChange: (next: T) => void;
};

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid gap-1.5">
      <Label className="text-xs font-medium uppercase tracking-wider">{label}</Label>
      {children}
      {hint && <div className="text-xs text-muted-foreground">{hint}</div>}
    </div>
  );
}

function ImageField({
  label,
  value,
  onChange,
  hint,
}: {
  label: string;
  value: string | null | undefined;
  onChange: (url: string | null) => void;
  hint?: string;
}) {
  const [showUpload, setShowUpload] = React.useState(false);
  const fieldId = React.useId();
  return (
    <Field label={label} hint={hint}>
      {value ? (
        <div className="flex items-center gap-3 rounded-xl border border-border bg-surface p-3">
          {/* eslint-disable-next-line @next/next/no-img-element -- preview only, no opt needed. */}
          <img src={value} alt="" className="h-14 w-14 rounded-lg object-cover bg-secondary" />
          <div className="min-w-0 flex-1">
            <div className="text-xs font-mono text-muted-foreground truncate">{value}</div>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setShowUpload((v) => !v)}
          >
            Replace
          </Button>
          <Button type="button" variant="outline" size="sm" onClick={() => onChange(null)}>
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      ) : (
        <div className="rounded-xl border border-dashed border-border bg-surface-soft p-3 text-xs text-muted-foreground inline-flex items-center gap-2">
          <ImageIcon className="h-3.5 w-3.5" />
          No image uploaded yet.
        </div>
      )}
      {(showUpload || !value) && (
        <div className="grid gap-2">
          <FileUpload
            name={`upload-${fieldId}`}
            endpoint="/uploads"
            folder="cms"
            accept="image/*"
            hint="JPG / PNG / WebP / SVG · up to 25 MB"
            onUploaded={(r: UploadResult) => {
              onChange(r.url);
              setShowUpload(false);
            }}
          />
          <div className="flex items-center justify-center gap-2 text-xs text-muted-foreground">
            <span className="h-px flex-1 bg-border" />
            <span>or</span>
            <span className="h-px flex-1 bg-border" />
          </div>
          <div className="flex justify-center">
            <MediaPickerButton
              imagesOnly
              onPick={(url) => {
                onChange(url);
                setShowUpload(false);
              }}
            />
          </div>
        </div>
      )}
    </Field>
  );
}

function ItemList<T>({
  label,
  items,
  defaults,
  onChange,
  renderItem,
  emptyHint,
}: {
  label: string;
  items: T[];
  defaults: () => T;
  onChange: (next: T[]) => void;
  renderItem: (item: T, i: number, update: (next: T) => void) => React.ReactNode;
  emptyHint?: string;
}) {
  function update(i: number, next: T) {
    onChange(items.map((it, idx) => (idx === i ? next : it)));
  }
  function remove(i: number) {
    onChange(items.filter((_, idx) => idx !== i));
  }
  function move(i: number, dir: -1 | 1) {
    const j = i + dir;
    if (j < 0 || j >= items.length) return;
    const copy = [...items];
    [copy[i], copy[j]] = [copy[j], copy[i]];
    onChange(copy);
  }
  return (
    <div className="grid gap-3">
      <div className="flex items-center justify-between">
        <Label className="text-xs font-medium uppercase tracking-wider">{label}</Label>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => onChange([...items, defaults()])}
        >
          <Plus className="h-3.5 w-3.5" /> Add
        </Button>
      </div>
      {items.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border bg-surface-soft p-4 text-xs text-muted-foreground">
          {emptyHint ?? "No items yet — click Add to start."}
        </div>
      ) : (
        <ol className="grid gap-2">
          {items.map((it, i) => (
            <li
              key={i}
              className="rounded-xl border border-border bg-surface-soft p-3 grid gap-3"
            >
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>#{i + 1}</span>
                <div className="flex gap-1">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={i === 0}
                    onClick={() => move(i, -1)}
                  >
                    ↑
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={i === items.length - 1}
                    onClick={() => move(i, 1)}
                  >
                    ↓
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => remove(i)}
                  >
                    <Trash2 className="h-3.5 w-3.5 text-rose-700" />
                  </Button>
                </div>
              </div>
              {renderItem(it, i, (next) => update(i, next))}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Forms — one per section type
// ---------------------------------------------------------------------------

function HeroForm({ section, onChange }: SectionFormProps<HeroSection>) {
  const set = (patch: Partial<HeroSection>) => onChange({ ...section, ...patch });
  return (
    <div className="grid gap-4">
      <Field label="Eyebrow" hint="Small uppercase label above the title.">
        <Input value={section.eyebrow ?? ""} onChange={(e) => set({ eyebrow: e.target.value || null })} />
      </Field>
      <Field label="Title">
        <Input value={section.title} onChange={(e) => set({ title: e.target.value })} required />
      </Field>
      <Field label="Subtitle">
        <Textarea value={section.subtitle ?? ""} onChange={(e) => set({ subtitle: e.target.value || null })} rows={2} />
      </Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Primary CTA label">
          <Input value={section.primary_cta_label ?? ""} onChange={(e) => set({ primary_cta_label: e.target.value || null })} />
        </Field>
        <Field label="Primary CTA link">
          <Input value={section.primary_cta_href ?? ""} onChange={(e) => set({ primary_cta_href: e.target.value || null })} placeholder="/contact" />
        </Field>
        <Field label="Secondary CTA label">
          <Input value={section.secondary_cta_label ?? ""} onChange={(e) => set({ secondary_cta_label: e.target.value || null })} />
        </Field>
        <Field label="Secondary CTA link">
          <Input value={section.secondary_cta_href ?? ""} onChange={(e) => set({ secondary_cta_href: e.target.value || null })} />
        </Field>
      </div>
      <Field label="Layout">
        <Select value={section.variant ?? "default"} onChange={(e) => set({ variant: e.target.value as HeroSection["variant"] })}>
          <option value="default">Default — left-aligned</option>
          <option value="centered">Centered</option>
          <option value="split">Split — image right</option>
        </Select>
      </Field>
      <ImageField
        label="Hero image (optional)"
        value={section.image_url}
        onChange={(url) => set({ image_url: url })}
        hint="Recommended 16:9 ratio. Hidden when no image is uploaded."
      />
    </div>
  );
}

function FeatureGridForm({ section, onChange }: SectionFormProps<FeatureGridSection>) {
  const set = (patch: Partial<FeatureGridSection>) => onChange({ ...section, ...patch });
  return (
    <div className="grid gap-4">
      <Field label="Eyebrow"><Input value={section.eyebrow ?? ""} onChange={(e) => set({ eyebrow: e.target.value || null })} /></Field>
      <Field label="Title"><Input value={section.title ?? ""} onChange={(e) => set({ title: e.target.value || null })} /></Field>
      <Field label="Subtitle"><Textarea value={section.subtitle ?? ""} onChange={(e) => set({ subtitle: e.target.value || null })} rows={2} /></Field>
      <Field label="Columns" hint="Number of items per row at desktop.">
        <Select value={String(section.columns ?? 3)} onChange={(e) => set({ columns: Number(e.target.value) })}>
          <option value="1">1</option>
          <option value="2">2</option>
          <option value="3">3</option>
          <option value="4">4</option>
        </Select>
      </Field>
      <ItemList<FeatureItem>
        label="Features"
        items={section.items}
        defaults={() => ({ title: "", body: "" })}
        onChange={(items) => set({ items })}
        renderItem={(it, _i, update) => (
          <div className="grid gap-2">
            <Input placeholder="Feature title" value={it.title} onChange={(e) => update({ ...it, title: e.target.value })} />
            <Textarea placeholder="Feature description" rows={2} value={it.body} onChange={(e) => update({ ...it, body: e.target.value })} />
          </div>
        )}
      />
    </div>
  );
}

function IconBadgeForm({ section, onChange }: SectionFormProps<IconBadgeSection>) {
  const set = (patch: Partial<IconBadgeSection>) => onChange({ ...section, ...patch });
  return (
    <div className="grid gap-4">
      <Field label="Title"><Input value={section.title} onChange={(e) => set({ title: e.target.value })} required /></Field>
      <Field label="Body"><Textarea value={section.body ?? ""} onChange={(e) => set({ body: e.target.value || null })} rows={3} /></Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="CTA label"><Input value={section.cta_label ?? ""} onChange={(e) => set({ cta_label: e.target.value || null })} /></Field>
        <Field label="CTA link"><Input value={section.cta_href ?? ""} onChange={(e) => set({ cta_href: e.target.value || null })} /></Field>
      </div>
    </div>
  );
}

function BigQuoteForm({ section, onChange }: SectionFormProps<BigQuoteSection>) {
  const set = (patch: Partial<BigQuoteSection>) => onChange({ ...section, ...patch });
  return (
    <div className="grid gap-4">
      <Field label="Quote"><Textarea value={section.quote} onChange={(e) => set({ quote: e.target.value })} rows={4} required /></Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Author"><Input value={section.author ?? ""} onChange={(e) => set({ author: e.target.value || null })} /></Field>
        <Field label="Role / company"><Input value={section.role ?? ""} onChange={(e) => set({ role: e.target.value || null })} /></Field>
      </div>
    </div>
  );
}

function FaqForm({ section, onChange }: SectionFormProps<FaqSection>) {
  const set = (patch: Partial<FaqSection>) => onChange({ ...section, ...patch });
  return (
    <div className="grid gap-4">
      <Field label="Title"><Input value={section.title ?? ""} onChange={(e) => set({ title: e.target.value || null })} /></Field>
      <Field label="Subtitle"><Textarea value={section.subtitle ?? ""} onChange={(e) => set({ subtitle: e.target.value || null })} rows={2} /></Field>
      <ItemList<FaqItem>
        label="Questions"
        items={section.items}
        defaults={() => ({ question: "", answer: "" })}
        onChange={(items) => set({ items })}
        renderItem={(it, _i, update) => (
          <div className="grid gap-2">
            <Input placeholder="Question" value={it.question} onChange={(e) => update({ ...it, question: e.target.value })} />
            <Textarea placeholder="Answer" rows={3} value={it.answer} onChange={(e) => update({ ...it, answer: e.target.value })} />
          </div>
        )}
      />
    </div>
  );
}

function StatStripForm({ section, onChange }: SectionFormProps<StatStripSection>) {
  const set = (patch: Partial<StatStripSection>) => onChange({ ...section, ...patch });
  return (
    <div className="grid gap-4">
      <Field label="Eyebrow"><Input value={section.eyebrow ?? ""} onChange={(e) => set({ eyebrow: e.target.value || null })} /></Field>
      <ItemList<StatItem>
        label="Stats"
        items={section.items}
        defaults={() => ({ value: "", label: "", caption: null })}
        onChange={(items) => set({ items })}
        renderItem={(it, _i, update) => (
          <div className="grid gap-2 sm:grid-cols-3">
            <Input placeholder="Value (e.g. 50k+)" value={it.value} onChange={(e) => update({ ...it, value: e.target.value })} />
            <Input placeholder="Label" value={it.label} onChange={(e) => update({ ...it, label: e.target.value })} />
            <Input placeholder="Caption (optional)" value={it.caption ?? ""} onChange={(e) => update({ ...it, caption: e.target.value || null })} />
          </div>
        )}
      />
    </div>
  );
}

function TestimonialsForm({ section, onChange }: SectionFormProps<TestimonialsSection>) {
  const set = (patch: Partial<TestimonialsSection>) => onChange({ ...section, ...patch });
  return (
    <div className="grid gap-4">
      <Field label="Eyebrow"><Input value={section.eyebrow ?? ""} onChange={(e) => set({ eyebrow: e.target.value || null })} /></Field>
      <Field label="Title"><Input value={section.title ?? ""} onChange={(e) => set({ title: e.target.value || null })} /></Field>
      <ItemList<TestimonialItem>
        label="Testimonials"
        items={section.items}
        defaults={() => ({ quote: "", author: "", role: null, company: null, headshot_url: null })}
        onChange={(items) => set({ items })}
        renderItem={(it, _i, update) => (
          <div className="grid gap-2">
            <Textarea placeholder="Quote" rows={3} value={it.quote} onChange={(e) => update({ ...it, quote: e.target.value })} />
            <div className="grid gap-2 sm:grid-cols-3">
              <Input placeholder="Author" value={it.author} onChange={(e) => update({ ...it, author: e.target.value })} />
              <Input placeholder="Role" value={it.role ?? ""} onChange={(e) => update({ ...it, role: e.target.value || null })} />
              <Input placeholder="Company" value={it.company ?? ""} onChange={(e) => update({ ...it, company: e.target.value || null })} />
            </div>
            <ImageField label="Headshot" value={it.headshot_url} onChange={(url) => update({ ...it, headshot_url: url })} />
          </div>
        )}
      />
    </div>
  );
}

function TimelineForm({ section, onChange }: SectionFormProps<TimelineSection>) {
  const set = (patch: Partial<TimelineSection>) => onChange({ ...section, ...patch });
  return (
    <div className="grid gap-4">
      <Field label="Title"><Input value={section.title ?? ""} onChange={(e) => set({ title: e.target.value || null })} /></Field>
      <ItemList<TimelineItem>
        label="Milestones"
        items={section.items}
        defaults={() => ({ date: "", title: "", body: "" })}
        onChange={(items) => set({ items })}
        renderItem={(it, _i, update) => (
          <div className="grid gap-2">
            <Input placeholder="Date / period (e.g. May 2025)" value={it.date} onChange={(e) => update({ ...it, date: e.target.value })} />
            <Input placeholder="Milestone title" value={it.title} onChange={(e) => update({ ...it, title: e.target.value })} />
            <Textarea placeholder="What happened" rows={2} value={it.body} onChange={(e) => update({ ...it, body: e.target.value })} />
          </div>
        )}
      />
    </div>
  );
}

function ProcessStepsForm({ section, onChange }: SectionFormProps<ProcessStepsSection>) {
  const set = (patch: Partial<ProcessStepsSection>) => onChange({ ...section, ...patch });
  return (
    <div className="grid gap-4">
      <Field label="Eyebrow"><Input value={section.eyebrow ?? ""} onChange={(e) => set({ eyebrow: e.target.value || null })} /></Field>
      <Field label="Title"><Input value={section.title ?? ""} onChange={(e) => set({ title: e.target.value || null })} /></Field>
      <ItemList<ProcessStepItem>
        label="Steps"
        items={section.items}
        defaults={() => ({ title: "", body: "" })}
        onChange={(items) => set({ items })}
        renderItem={(it, _i, update) => (
          <div className="grid gap-2">
            <Input placeholder="Step title" value={it.title} onChange={(e) => update({ ...it, title: e.target.value })} />
            <Textarea placeholder="Step description" rows={2} value={it.body} onChange={(e) => update({ ...it, body: e.target.value })} />
          </div>
        )}
      />
    </div>
  );
}

function LogoCloudForm({ section, onChange }: SectionFormProps<LogoCloudSection>) {
  const set = (patch: Partial<LogoCloudSection>) => onChange({ ...section, ...patch });
  return (
    <div className="grid gap-4">
      <Field label="Eyebrow"><Input value={section.eyebrow ?? ""} onChange={(e) => set({ eyebrow: e.target.value || null })} /></Field>
      <Field label="Title"><Input value={section.title ?? ""} onChange={(e) => set({ title: e.target.value || null })} /></Field>
      <ItemList<LogoItem>
        label="Logos"
        items={section.items}
        defaults={() => ({ name: "", logo_url: "", href: null })}
        onChange={(items) => set({ items })}
        renderItem={(it, _i, update) => (
          <div className="grid gap-2">
            <Input placeholder="Brand name" value={it.name} onChange={(e) => update({ ...it, name: e.target.value })} />
            <ImageField label="Logo image" value={it.logo_url || null} onChange={(url) => update({ ...it, logo_url: url ?? "" })} />
            <Input placeholder="Link (optional)" value={it.href ?? ""} onChange={(e) => update({ ...it, href: e.target.value || null })} />
          </div>
        )}
      />
    </div>
  );
}

function CtaForm({ section, onChange }: SectionFormProps<CtaSection>) {
  const set = (patch: Partial<CtaSection>) => onChange({ ...section, ...patch });
  return (
    <div className="grid gap-4">
      <Field label="Eyebrow"><Input value={section.eyebrow ?? ""} onChange={(e) => set({ eyebrow: e.target.value || null })} /></Field>
      <Field label="Title"><Input value={section.title} onChange={(e) => set({ title: e.target.value })} required /></Field>
      <Field label="Subtitle"><Textarea value={section.subtitle ?? ""} onChange={(e) => set({ subtitle: e.target.value || null })} rows={2} /></Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Primary CTA label"><Input value={section.primary_cta_label ?? ""} onChange={(e) => set({ primary_cta_label: e.target.value || null })} /></Field>
        <Field label="Primary CTA link"><Input value={section.primary_cta_href ?? ""} onChange={(e) => set({ primary_cta_href: e.target.value || null })} /></Field>
        <Field label="Secondary CTA label"><Input value={section.secondary_cta_label ?? ""} onChange={(e) => set({ secondary_cta_label: e.target.value || null })} /></Field>
        <Field label="Secondary CTA link"><Input value={section.secondary_cta_href ?? ""} onChange={(e) => set({ secondary_cta_href: e.target.value || null })} /></Field>
      </div>
    </div>
  );
}

function NewsletterCtaForm({ section, onChange }: SectionFormProps<NewsletterCtaSection>) {
  const set = (patch: Partial<NewsletterCtaSection>) => onChange({ ...section, ...patch });
  return (
    <div className="grid gap-4">
      <Field label="Eyebrow"><Input value={section.eyebrow ?? ""} onChange={(e) => set({ eyebrow: e.target.value || null })} /></Field>
      <Field label="Title"><Input value={section.title ?? ""} onChange={(e) => set({ title: e.target.value || null })} /></Field>
      <Field label="Subtitle"><Textarea value={section.subtitle ?? ""} onChange={(e) => set({ subtitle: e.target.value || null })} rows={2} /></Field>
    </div>
  );
}

function RichTextForm({ section, onChange }: SectionFormProps<RichTextSection>) {
  const set = (patch: Partial<RichTextSection>) => onChange({ ...section, ...patch });
  return (
    <div className="grid gap-4">
      <Field label="Width">
        <Select value={section.width ?? "default"} onChange={(e) => set({ width: e.target.value as RichTextSection["width"] })}>
          <option value="narrow">Narrow (max-w-2xl)</option>
          <option value="default">Default (max-w-3xl)</option>
          <option value="wide">Wide (max-w-5xl)</option>
        </Select>
      </Field>
      <Field label="Body" hint="Plain text or markdown. Two newlines start a new paragraph.">
        <Textarea value={section.body} onChange={(e) => set({ body: e.target.value })} rows={10} required />
      </Field>
    </div>
  );
}

function ImageTextForm({ section, onChange }: SectionFormProps<ImageTextSection>) {
  const set = (patch: Partial<ImageTextSection>) => onChange({ ...section, ...patch });
  return (
    <div className="grid gap-4">
      <Field label="Eyebrow"><Input value={section.eyebrow ?? ""} onChange={(e) => set({ eyebrow: e.target.value || null })} /></Field>
      <Field label="Title"><Input value={section.title ?? ""} onChange={(e) => set({ title: e.target.value || null })} /></Field>
      <Field label="Body"><Textarea value={section.body} onChange={(e) => set({ body: e.target.value })} rows={6} required /></Field>
      <ImageField label="Image" value={section.image_url} onChange={(url) => set({ image_url: url })} />
      <Field label="Image position">
        <Select value={section.image_position ?? "right"} onChange={(e) => set({ image_position: e.target.value as ImageTextSection["image_position"] })}>
          <option value="right">Right (image right of text)</option>
          <option value="left">Left (image left of text)</option>
        </Select>
      </Field>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Dispatch table
// ---------------------------------------------------------------------------

export type AnyForm = (props: SectionFormProps<Section>) => React.ReactElement;

export const SECTION_FORMS: Record<Section["type"], AnyForm> = {
  hero: HeroForm as AnyForm,
  feature_grid: FeatureGridForm as AnyForm,
  icon_badge: IconBadgeForm as AnyForm,
  big_quote: BigQuoteForm as AnyForm,
  faq: FaqForm as AnyForm,
  stat_strip: StatStripForm as AnyForm,
  testimonials: TestimonialsForm as AnyForm,
  timeline: TimelineForm as AnyForm,
  process_steps: ProcessStepsForm as AnyForm,
  logo_cloud: LogoCloudForm as AnyForm,
  cta: CtaForm as AnyForm,
  newsletter_cta: NewsletterCtaForm as AnyForm,
  rich_text: RichTextForm as AnyForm,
  image_text: ImageTextForm as AnyForm,
};

// Default values for newly added sections (server fills `id` on first save).
export const NEW_SECTION_DEFAULTS: Record<Section["type"], () => Section> = {
  hero: () => ({ id: tmpId(), type: "hero", title: "Headline goes here", visible: true, variant: "default" }),
  feature_grid: () => ({ id: tmpId(), type: "feature_grid", visible: true, columns: 3, items: [{ title: "", body: "" }] }),
  icon_badge: () => ({ id: tmpId(), type: "icon_badge", visible: true, title: "" }),
  big_quote: () => ({ id: tmpId(), type: "big_quote", visible: true, quote: "" }),
  faq: () => ({ id: tmpId(), type: "faq", visible: true, items: [{ question: "", answer: "" }] }),
  stat_strip: () => ({ id: tmpId(), type: "stat_strip", visible: true, items: [{ value: "", label: "" }] }),
  testimonials: () => ({ id: tmpId(), type: "testimonials", visible: true, items: [{ quote: "", author: "" }] }),
  timeline: () => ({ id: tmpId(), type: "timeline", visible: true, items: [{ date: "", title: "", body: "" }] }),
  process_steps: () => ({ id: tmpId(), type: "process_steps", visible: true, items: [{ title: "", body: "" }] }),
  logo_cloud: () => ({ id: tmpId(), type: "logo_cloud", visible: true, items: [] }),
  cta: () => ({ id: tmpId(), type: "cta", visible: true, title: "" }),
  newsletter_cta: () => ({ id: tmpId(), type: "newsletter_cta", visible: true }),
  rich_text: () => ({ id: tmpId(), type: "rich_text", visible: true, body: "", width: "default" }),
  image_text: () => ({ id: tmpId(), type: "image_text", visible: true, body: "", image_position: "right" }),
};

function tmpId(): string {
  return "tmp_" + Math.random().toString(36).slice(2, 14);
}
