"use client";

/**
 * Client-side preview wrapper around the shared markdown renderer in
 * `lib/markdown.ts`. The pure renderer lives there so the public-site
 * Server Components can use it too without dragging a "use client" boundary.
 */

import * as React from "react";
import { renderMarkdownToHtml } from "@/lib/markdown";

export function MarkdownPreview({
  source,
  className = "",
}: {
  source: string;
  className?: string;
}) {
  const html = React.useMemo(() => renderMarkdownToHtml(source), [source]);
  if (!source.trim()) {
    return (
      <div className={`text-sm text-muted-foreground italic ${className}`}>
        Nothing to preview yet — write some markdown on the left.
      </div>
    );
  }
  return (
    <div
      className={`text-sm text-foreground/90 ${className}`}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
