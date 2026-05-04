"use client";

/**
 * Pure-SVG charts. No chart library dependency.
 *
 * - SparkLine: tiny inline trend line
 * - BarChart: vertical bars with axes
 * - LineChart: smooth area line with optional baseline grid
 */

import * as React from "react";
import { cn } from "@/lib/utils";

export type Point = { date: string; value: number };

export function SparkLine({
  points,
  className,
  height = 36,
  width = 120,
}: {
  points: Point[];
  className?: string;
  height?: number;
  width?: number;
}) {
  if (points.length === 0) return <div className={cn("text-xs text-muted-foreground", className)}>—</div>;
  const max = Math.max(1, ...points.map((p) => p.value));
  const step = width / Math.max(points.length - 1, 1);
  const path = points
    .map((p, i) => {
      const x = i * step;
      const y = height - (p.value / max) * height;
      return `${i === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");

  return (
    <svg viewBox={`0 0 ${width} ${height}`} width={width} height={height} className={className}>
      <path d={path} fill="none" stroke="currentColor" strokeWidth={1.5} className="text-primary" />
    </svg>
  );
}

export function BarChart({
  points,
  height = 200,
  label = "value",
  color = "var(--brand)",
}: {
  points: Point[];
  height?: number;
  label?: string;
  color?: string;
}) {
  const [hover, setHover] = React.useState<number | null>(null);
  if (points.length === 0) return <div className="text-xs text-muted-foreground">No data.</div>;
  const max = Math.max(1, ...points.map((p) => p.value));
  const total = points.reduce((s, p) => s + p.value, 0);
  return (
    <div>
      <div
        className="grid items-end gap-1.5"
        style={{ gridTemplateColumns: `repeat(${points.length}, minmax(0, 1fr))`, height }}
      >
        {points.map((p, i) => {
          const h = (p.value / max) * 100;
          const isHover = hover === i;
          return (
            <button
              key={p.date}
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
              className="group relative flex h-full items-end"
              aria-label={`${p.date}: ${p.value} ${label}`}
            >
              <div
                className="w-full rounded-t-md transition-all"
                style={{
                  height: `${Math.max(h, 2)}%`,
                  background: color,
                  opacity: isHover ? 1 : 0.85,
                }}
              />
              {isHover && (
                <div className="absolute left-1/2 -top-9 -translate-x-1/2 whitespace-nowrap rounded-md bg-ink text-white px-2 py-1 text-[10px]">
                  <div className="font-semibold">{p.value}</div>
                  <div className="opacity-70">{p.date}</div>
                </div>
              )}
            </button>
          );
        })}
      </div>
      <div className="mt-3 flex items-center justify-between text-[11px] text-muted-foreground">
        <span>{points[0].date}</span>
        <span className="text-foreground font-medium">{total.toLocaleString()} total {label}</span>
        <span>{points[points.length - 1].date}</span>
      </div>
    </div>
  );
}

export function LineChart({
  points,
  height = 220,
  label = "value",
}: {
  points: Point[];
  height?: number;
  label?: string;
}) {
  const [hover, setHover] = React.useState<number | null>(null);
  const width = 800;
  const padding = { top: 16, right: 16, bottom: 24, left: 32 };
  const innerW = width - padding.left - padding.right;
  const innerH = height - padding.top - padding.bottom;

  if (points.length === 0) return <div className="text-xs text-muted-foreground">No data.</div>;

  const max = Math.max(1, ...points.map((p) => p.value));
  const step = innerW / Math.max(points.length - 1, 1);

  const linePoints = points.map((p, i) => {
    const x = padding.left + i * step;
    const y = padding.top + (innerH - (p.value / max) * innerH);
    return { x, y, p };
  });

  const path = linePoints
    .map((pt, i) => `${i === 0 ? "M" : "L"}${pt.x.toFixed(2)},${pt.y.toFixed(2)}`)
    .join(" ");
  const areaPath = `${path} L${padding.left + innerW},${padding.top + innerH} L${padding.left},${padding.top + innerH} Z`;

  const yTicks = 4;
  const tickValues = Array.from({ length: yTicks + 1 }, (_, i) => Math.round((max / yTicks) * (yTicks - i)));

  function onMove(e: React.MouseEvent<SVGSVGElement>) {
    const svg = e.currentTarget;
    const rect = svg.getBoundingClientRect();
    const xPct = (e.clientX - rect.left) / rect.width;
    const i = Math.round(xPct * (points.length - 1));
    if (i >= 0 && i < points.length) setHover(i);
  }

  return (
    <div className="overflow-hidden">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full h-auto"
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
      >
        {/* Y grid lines + labels */}
        {tickValues.map((tv, i) => {
          const y = padding.top + (innerH * i) / yTicks;
          return (
            <g key={i}>
              <line
                x1={padding.left}
                y1={y}
                x2={padding.left + innerW}
                y2={y}
                stroke="currentColor"
                className="text-border"
                strokeDasharray={i === yTicks ? "0" : "2 4"}
                strokeWidth={1}
              />
              <text
                x={padding.left - 6}
                y={y + 3}
                textAnchor="end"
                className="fill-muted-foreground text-[10px]"
              >
                {tv}
              </text>
            </g>
          );
        })}

        {/* Area + line */}
        <defs>
          <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--brand)" stopOpacity="0.25" />
            <stop offset="100%" stopColor="var(--brand)" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={areaPath} fill="url(#areaGradient)" />
        <path d={path} fill="none" stroke="var(--brand)" strokeWidth={2} />

        {/* Hover marker */}
        {hover !== null && linePoints[hover] && (
          <g>
            <line
              x1={linePoints[hover].x}
              y1={padding.top}
              x2={linePoints[hover].x}
              y2={padding.top + innerH}
              stroke="var(--brand)"
              strokeOpacity={0.4}
              strokeWidth={1}
            />
            <circle cx={linePoints[hover].x} cy={linePoints[hover].y} r={4} fill="var(--brand)" />
            <g>
              <rect
                x={Math.min(linePoints[hover].x + 8, width - 110)}
                y={Math.max(linePoints[hover].y - 30, padding.top)}
                width={100}
                height={28}
                rx={4}
                fill="#0F1216"
              />
              <text
                x={Math.min(linePoints[hover].x + 14, width - 104)}
                y={Math.max(linePoints[hover].y - 16, padding.top + 14)}
                className="fill-white text-[10px] font-semibold"
              >
                {linePoints[hover].p.value} {label}
              </text>
              <text
                x={Math.min(linePoints[hover].x + 14, width - 104)}
                y={Math.max(linePoints[hover].y - 4, padding.top + 26)}
                className="fill-white/70 text-[9px]"
              >
                {linePoints[hover].p.date}
              </text>
            </g>
          </g>
        )}
      </svg>
    </div>
  );
}
