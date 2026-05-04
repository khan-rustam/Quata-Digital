"use client";

import * as React from "react";
import Image from "next/image";
import { cn } from "@/lib/utils";

/**
 * BrandImage — image slot with a brand-themed gradient fallback.
 *
 * Drop a real PNG/JPG at the `src` path inside `public/` and the image
 * takes over. Until then, the component renders a beautiful gradient panel
 * styled with the brand tokens so the page never looks empty or broken.
 *
 * Usage:
 *   <BrandImage
 *     src="/images/partners/service/hero.jpg"
 *     alt="Service partner on a delivery in Bamenda"
 *     width={1200}
 *     height={900}
 *     accent="emerald"
 *   />
 *
 * The fallback is the same regardless of whether the file is missing or
 * the user is offline — so if the boss hasn't sourced an image yet, the
 * page still ships looking polished.
 */

const ACCENTS = {
  brand: "from-primary/85 via-primary to-emerald-400",
  emerald: "from-emerald-700/85 via-emerald-500 to-emerald-300",
  amber: "from-amber-600/85 via-amber-400 to-amber-200",
  sky: "from-sky-600/85 via-sky-400 to-cyan-300",
  rose: "from-rose-600/85 via-rose-400 to-orange-300",
  violet: "from-violet-600/85 via-violet-400 to-fuchsia-300",
  ink: "from-ink via-zinc-700 to-zinc-500",
} as const;

export type BrandImageAccent = keyof typeof ACCENTS;

export function BrandImage({
  src,
  alt,
  width,
  height,
  accent = "brand",
  rounded = "rounded-3xl",
  className,
  caption,
  priority = false,
}: {
  src: string;
  alt: string;
  width: number;
  height: number;
  accent?: BrandImageAccent;
  rounded?: string;
  className?: string;
  caption?: string;
  priority?: boolean;
}) {
  const [loaded, setLoaded] = React.useState(false);
  const [errored, setErrored] = React.useState(false);

  const showImage = loaded && !errored;

  return (
    <figure className={cn("relative", className)}>
      <div
        className={cn(
          "relative overflow-hidden border border-border ring-soft",
          rounded
        )}
        style={{ aspectRatio: `${width} / ${height}` }}
      >
        {/* Brand gradient backdrop — always renders behind the image so the
            crossfade-in feels intentional and the fallback (when image is
            missing) looks like a deliberate brand panel. */}
        <div
          className={cn(
            "absolute inset-0 bg-linear-to-br",
            ACCENTS[accent]
          )}
        />
        <div className="absolute inset-0 dot-grid opacity-30" />
        {/* Subtle "Q" mark watermark in the fallback. */}
        <div
          className="absolute right-4 bottom-3 text-white/30 select-none pointer-events-none"
          style={{ fontSize: "min(40%, 240px)", fontWeight: 800, lineHeight: 1, letterSpacing: -8 }}
          aria-hidden
        >
          Q
        </div>

        {/* The real image — fades in over the gradient when it loads. */}
        <Image
          src={src}
          alt={alt}
          width={width}
          height={height}
          priority={priority}
          onLoad={() => setLoaded(true)}
          onError={() => setErrored(true)}
          className={cn(
            "absolute inset-0 h-full w-full object-cover transition-opacity duration-500",
            showImage ? "opacity-100" : "opacity-0"
          )}
        />
      </div>
      {caption && (
        <figcaption className="mt-3 text-xs text-muted-foreground">{caption}</figcaption>
      )}
    </figure>
  );
}
