"use client";

import * as React from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { PageShell } from "@/components/admin/page-shell";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { DataTable, type Column } from "@/components/admin/data-table";
import { FormDialog } from "@/components/admin/form-dialog";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select } from "@/components/ui/select";
import { TableSkeleton } from "@/components/ui/skeleton";
import { FileUpload } from "@/components/forms/file-upload";
import { MarkdownPreview } from "@/components/admin/markdown";
import { Eye, Pencil as PencilIcon } from "lucide-react";
import { useApi, useApiAction } from "@/lib/use-api";
import { useToast } from "@/components/ui/toast";
import { formatDate } from "@/lib/utils";

type Post = {
  id: number;
  slug: string;
  title: string;
  excerpt: string;
  body: string;
  category: string;
  cover_image_url: string | null;
  is_published: boolean;
  published_at: string | null;
  author: string;
};

type Page = {
  id: number;
  slug: string;
  title: string;
  content: string;
  is_published: boolean;
  updated_at: string;
};

export default function CmsPage() {
  return (
    <PageShell
      title="CMS"
      description="Edit homepage content, manage product pages and write blog posts."
      requirePermission="content:manage"
    >
      <Tabs defaultValue="posts">
        <TabsList>
          <TabsTrigger value="posts">Blog posts</TabsTrigger>
          <TabsTrigger value="pages">Static pages</TabsTrigger>
        </TabsList>
        <TabsContent value="posts">
          <PostsManager />
        </TabsContent>
        <TabsContent value="pages">
          <PagesManager />
        </TabsContent>
      </Tabs>
    </PageShell>
  );
}

function PostsManager() {
  const { data, loading, refresh } = useApi<Post[]>("/admin/blog");
  const action = useApiAction();
  const toast = useToast();
  const [open, setOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<Post | null>(null);
  const [deleting, setDeleting] = React.useState<Post | null>(null);

  async function onSubmit(form: FormData) {
    const payload = {
      slug: String(form.get("slug")),
      title: String(form.get("title")),
      excerpt: String(form.get("excerpt")),
      body: String(form.get("body")),
      category: String(form.get("category") || "Insight"),
      cover_image_url: String(form.get("cover_image_url") || "") || null,
      is_published: form.get("is_published") === "on",
    };
    try {
      if (editing) {
        await action(`/admin/blog/${editing.id}`, { method: "PUT", body: JSON.stringify(payload) });
        toast.success("Post updated", payload.title);
      } else {
        await action("/admin/blog", { method: "POST", body: JSON.stringify(payload) });
        toast.success("Post published", payload.title);
      }
      setOpen(false);
      refresh();
    } catch (err) {
      toast.error("Couldn't save", err instanceof Error ? err.message : "Try again.");
    }
  }

  async function onDelete() {
    if (!deleting) return;
    try {
      await action(`/admin/blog/${deleting.id}`, { method: "DELETE" });
      toast.success("Post removed", deleting.title);
      refresh();
    } catch (err) {
      toast.error("Couldn't delete", err instanceof Error ? err.message : "Try again.");
    } finally {
      setDeleting(null);
    }
  }

  const columns: Column<Post>[] = [
    { key: "title", header: "Title", cell: (r) => <span className="font-medium">{r.title}</span> },
    { key: "category", header: "Category", cell: (r) => <Badge variant="brand">{r.category}</Badge> },
    { key: "author", header: "Author", cell: (r) => r.author },
    {
      key: "status",
      header: "Status",
      cell: (r) => (
        <Badge variant={r.is_published ? "success" : "outline"}>
          {r.is_published ? "Published" : "Draft"}
        </Badge>
      ),
    },
    { key: "date", header: "Date", cell: (r) => (r.published_at ? formatDate(r.published_at) : "—") },
    {
      key: "actions",
      header: "",
      className: "w-32 text-right",
      cell: (r) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="ghost" onClick={() => { setEditing(r); setOpen(true); }}>
            <Pencil className="h-3.5 w-3.5" />
          </Button>
          <Button size="sm" variant="ghost" className="text-rose-700" onClick={() => setDeleting(r)}>
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      ),
    },
  ];

  return (
    <>
      <div className="mb-3 flex justify-end">
        <Button onClick={() => { setEditing(null); setOpen(true); }}>
          <Plus className="h-4 w-4" /> New post
        </Button>
      </div>
      {loading ? (
        <TableSkeleton rows={6} cols={6} />
      ) : (
        <DataTable columns={columns} rows={data ?? []} loading={false} empty="No posts yet." />
      )}

      <FormDialog
        open={open}
        onOpenChange={setOpen}
        title={editing ? `Edit "${editing.title}"` : "New blog post"}
        onSubmit={onSubmit}
        size="xl"
        submitLabel={editing ? "Save changes" : "Publish"}
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="slug">Slug *</Label>
            <Input id="slug" name="slug" required defaultValue={editing?.slug} />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="category">Category</Label>
            <Select id="category" name="category" defaultValue={editing?.category ?? "Insight"}>
              <option>Insight</option>
              <option>Product</option>
              <option>Company</option>
              <option>Engineering</option>
            </Select>
          </div>
        </div>
        <div className="grid gap-2">
          <Label htmlFor="title">Title *</Label>
          <Input id="title" name="title" required defaultValue={editing?.title} />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="excerpt">Excerpt *</Label>
          <Textarea id="excerpt" name="excerpt" rows={2} required defaultValue={editing?.excerpt} />
        </div>
        <div className="grid gap-2">
          <div className="flex items-center justify-between">
            <Label htmlFor="body">Body *</Label>
            <span className="text-[11px] text-muted-foreground">Markdown supported</span>
          </div>
          <BlogBodyEditor defaultValue={editing?.body ?? ""} />
        </div>
        <div className="grid gap-2">
          <Label>Cover image</Label>
          <FileUpload
            name="cover_image_url"
            folder="blog"
            endpoint="/uploads"
            accept="image/*"
            hint="JPG, PNG, WebP — up to 25 MB"
          />
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            name="is_published"
            defaultChecked={editing?.is_published ?? false}
            className="h-4 w-4 rounded border-border"
          />
          Publish immediately
        </label>
      </FormDialog>

      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(v) => !v && setDeleting(null)}
        title={`Delete "${deleting?.title ?? "post"}"?`}
        description="This permanently removes the post."
        confirmLabel="Delete"
        destructive
        onConfirm={onDelete}
      />
    </>
  );
}

function PagesManager() {
  const { data, loading, refresh } = useApi<Page[]>("/admin/pages");
  const action = useApiAction();
  const toast = useToast();
  const [open, setOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<Page | null>(null);
  const [deleting, setDeleting] = React.useState<Page | null>(null);

  async function onSubmit(form: FormData) {
    const payload = {
      slug: String(form.get("slug")),
      title: String(form.get("title")),
      content: String(form.get("content")),
      is_published: form.get("is_published") === "on",
    };
    try {
      if (editing) {
        await action(`/admin/pages/${editing.id}`, { method: "PUT", body: JSON.stringify(payload) });
        toast.success("Page updated", payload.title);
      } else {
        await action("/admin/pages", { method: "POST", body: JSON.stringify(payload) });
        toast.success("Page created", payload.title);
      }
      setOpen(false);
      refresh();
    } catch (err) {
      toast.error("Couldn't save", err instanceof Error ? err.message : "Try again.");
    }
  }

  async function onDelete() {
    if (!deleting) return;
    try {
      await action(`/admin/pages/${deleting.id}`, { method: "DELETE" });
      toast.success("Page removed", deleting.title);
      refresh();
    } catch (err) {
      toast.error("Couldn't delete", err instanceof Error ? err.message : "Try again.");
    } finally {
      setDeleting(null);
    }
  }

  const columns: Column<Page>[] = [
    { key: "title", header: "Page", cell: (r) => <span className="font-medium">{r.title}</span> },
    { key: "slug", header: "Slug", cell: (r) => <code className="text-xs">/{r.slug}</code> },
    {
      key: "status",
      header: "Status",
      cell: (r) => (
        <Badge variant={r.is_published ? "success" : "outline"}>
          {r.is_published ? "Published" : "Draft"}
        </Badge>
      ),
    },
    { key: "updated", header: "Updated", cell: (r) => formatDate(r.updated_at) },
    {
      key: "actions",
      header: "",
      className: "w-32 text-right",
      cell: (r) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="ghost" onClick={() => { setEditing(r); setOpen(true); }}>
            <Pencil className="h-3.5 w-3.5" />
          </Button>
          <Button size="sm" variant="ghost" className="text-rose-700" onClick={() => setDeleting(r)}>
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      ),
    },
  ];

  return (
    <>
      <div className="mb-3 flex justify-end">
        <Button onClick={() => { setEditing(null); setOpen(true); }}>
          <Plus className="h-4 w-4" /> New page
        </Button>
      </div>
      {loading ? (
        <TableSkeleton rows={4} cols={5} />
      ) : (
        <DataTable columns={columns} rows={data ?? []} loading={false} empty="No pages yet." />
      )}

      <FormDialog
        open={open}
        onOpenChange={setOpen}
        title={editing ? `Edit "${editing.title}"` : "New CMS page"}
        onSubmit={onSubmit}
        size="lg"
        submitLabel={editing ? "Save changes" : "Create page"}
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="slug">Slug *</Label>
            <Input id="slug" name="slug" required defaultValue={editing?.slug} />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="title">Title *</Label>
            <Input id="title" name="title" required defaultValue={editing?.title} />
          </div>
        </div>
        <div className="grid gap-2">
          <Label htmlFor="content">Content *</Label>
          <Textarea id="content" name="content" rows={12} required defaultValue={editing?.content} />
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            name="is_published"
            defaultChecked={editing?.is_published ?? true}
            className="h-4 w-4 rounded border-border"
          />
          Publish
        </label>
      </FormDialog>

      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(v) => !v && setDeleting(null)}
        title={`Delete "${deleting?.title ?? "page"}"?`}
        confirmLabel="Delete"
        destructive
        onConfirm={onDelete}
      />
    </>
  );
}

function BlogBodyEditor({ defaultValue }: { defaultValue: string }) {
  const [value, setValue] = React.useState(defaultValue);
  const [tab, setTab] = React.useState<"write" | "preview">("write");

  return (
    <div className="rounded-2xl border border-border bg-surface overflow-hidden">
      <div className="flex items-center justify-between border-b border-border bg-surface-soft px-3 py-1.5">
        <div className="inline-flex items-center gap-1 rounded-full border border-border bg-surface p-0.5 text-xs">
          <button
            type="button"
            onClick={() => setTab("write")}
            className={`inline-flex items-center gap-1 rounded-full px-3 py-1 transition ${
              tab === "write" ? "bg-secondary text-foreground" : "text-muted-foreground"
            }`}
          >
            <PencilIcon className="h-3 w-3" /> Write
          </button>
          <button
            type="button"
            onClick={() => setTab("preview")}
            className={`inline-flex items-center gap-1 rounded-full px-3 py-1 transition ${
              tab === "preview" ? "bg-secondary text-foreground" : "text-muted-foreground"
            }`}
          >
            <Eye className="h-3 w-3" /> Preview
          </button>
        </div>
        <div className="text-[11px] text-muted-foreground">{value.length} chars</div>
      </div>
      {/* Always-rendered hidden textarea so the FormDialog still gets the value via FormData */}
      <textarea
        name="body"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        required
        className={`block w-full bg-transparent p-4 text-sm font-mono outline-none min-h-[260px] resize-y ${
          tab === "write" ? "" : "hidden"
        }`}
        placeholder={"# Heading\n\nWrite your post in **Markdown**.\n\n- Lists\n- [Links](https://quatadigital.com)\n- `code`"}
      />
      {tab === "preview" && (
        <div className="max-h-[420px] overflow-y-auto bg-card p-5">
          <MarkdownPreview source={value} />
        </div>
      )}
    </div>
  );
}
