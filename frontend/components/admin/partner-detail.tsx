"use client";

import * as React from "react";
import { Loader2, Save } from "lucide-react";
import { SlideOver, SlideOverContent } from "@/components/admin/slide-over";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { useApi, useApiAction } from "@/lib/use-api";
import { useToast } from "@/components/ui/toast";

type PartnerDetail = {
  id: number;
  partner_type: "business" | "strategic" | "investor" | "service";
  status: "new" | "in_review" | "approved" | "rejected";
  payload: Record<string, string>;
  notes: string;
  created_at: string;
  updated_at: string;
};

const statusVariant: Record<PartnerDetail["status"], "default" | "warn" | "success" | "danger"> = {
  new: "default",
  in_review: "warn",
  approved: "success",
  rejected: "danger",
};

export function PartnerDetailSlideOver({
  open,
  onOpenChange,
  partnerId,
  onChanged,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  partnerId: number | null;
  onChanged: () => void;
}) {
  const path = open && partnerId ? `/admin/partners/${partnerId}` : null;
  const { data, loading } = useApi<PartnerDetail>(path);
  const action = useApiAction();
  const toast = useToast();

  const [notes, setNotes] = React.useState("");
  const [saving, setSaving] = React.useState(false);

  React.useEffect(() => {
    if (data) setNotes(data.notes ?? "");
  }, [data]);

  async function setStatus(status: PartnerDetail["status"]) {
    if (!partnerId) return;
    try {
      await action(`/admin/partners/${partnerId}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      toast.success(`Marked ${status.replace("_", " ")}`);
      onChanged();
    } catch (err) {
      toast.error("Couldn't update", err instanceof Error ? err.message : "Try again.");
    }
  }

  async function saveNotes() {
    if (!partnerId) return;
    setSaving(true);
    try {
      await action(`/admin/partners/${partnerId}/notes`, {
        method: "PUT",
        body: JSON.stringify({ notes }),
      });
      toast.success("Notes saved");
      onChanged();
    } catch (err) {
      toast.error("Couldn't save", err instanceof Error ? err.message : "Try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <SlideOver open={open} onOpenChange={onOpenChange}>
      <SlideOverContent
        title={data ? `Partner request #${data.id}` : "Partner request"}
        description={data ? `${data.partner_type} · submitted ${new Date(data.created_at).toLocaleString()}` : ""}
        size="lg"
      >
        {loading || !data ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <div className="space-y-6">
            {/* Status + actions */}
            <div className="rounded-2xl border border-border bg-surface-soft p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-xs uppercase tracking-wider text-muted-foreground">Status</div>
                  <Badge variant={statusVariant[data.status]} className="mt-1 capitalize">
                    {data.status.replace("_", " ")}
                  </Badge>
                </div>
                <div className="flex gap-1.5 flex-wrap justify-end">
                  <Button size="sm" variant="outline" onClick={() => setStatus("in_review")}>
                    Review
                  </Button>
                  <Button size="sm" onClick={() => setStatus("approved")}>
                    Approve
                  </Button>
                  <Button size="sm" variant="ghost" className="text-rose-700" onClick={() => setStatus("rejected")}>
                    Reject
                  </Button>
                </div>
              </div>
            </div>

            {/* Payload table */}
            <div>
              <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                Submitted information
              </div>
              <dl className="rounded-2xl border border-border bg-card overflow-hidden">
                {Object.entries(data.payload).map(([k, v], i) => (
                  <div
                    key={k}
                    className={`grid grid-cols-3 gap-2 px-4 py-3 text-sm ${
                      i !== 0 ? "border-t border-border" : ""
                    }`}
                  >
                    <dt className="text-muted-foreground text-xs uppercase tracking-wider self-center">
                      {k.replace(/_/g, " ")}
                    </dt>
                    <dd className="col-span-2 break-words">{String(v)}</dd>
                  </div>
                ))}
                {Object.keys(data.payload).length === 0 && (
                  <div className="px-4 py-6 text-sm text-muted-foreground text-center">
                    No payload submitted.
                  </div>
                )}
              </dl>
            </div>

            {/* Internal notes */}
            <div>
              <Label htmlFor="notes" className="mb-2 inline-block">Internal notes</Label>
              <Textarea
                id="notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={6}
                placeholder="Notes only visible to internal team — context, calls, decisions made…"
              />
              <div className="mt-3 flex items-center justify-between">
                <div className="text-xs text-muted-foreground">{notes.length}/1000</div>
                <Button size="sm" onClick={saveNotes} disabled={saving}>
                  {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
                  Save notes
                </Button>
              </div>
            </div>

            {/* Meta */}
            <div className="text-xs text-muted-foreground border-t border-border pt-3">
              Last updated {new Date(data.updated_at).toLocaleString()}
            </div>
          </div>
        )}
      </SlideOverContent>
    </SlideOver>
  );
}
