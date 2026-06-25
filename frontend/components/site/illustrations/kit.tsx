/**
 * SVG illustration kit — shared, composable primitives.
 *
 * Every public illustration is assembled from these pieces so the whole set
 * shares one flat, modern "product-mockup" style. Pure presentational SVG
 * fragments (no client state) — safe in Server Components.
 *
 * Conventions:
 *  - All coordinates are absolute within the parent <svg> viewBox.
 *  - Flat fills only; no <defs>/url() so illustrations never collide on ids.
 *  - Lucide glyphs are embedded via <IconGlyph> for instant topical relevance.
 */
import * as React from "react";
import type { LucideIcon } from "lucide-react";
import { C } from "./palette";

/** A grid of small dots — ambient texture without a <pattern> def. */
export function Dots({
  x,
  y,
  cols,
  rows,
  gap = 22,
  r = 2,
  color = C.blue,
  opacity = 0.18,
}: {
  x: number;
  y: number;
  cols: number;
  rows: number;
  gap?: number;
  r?: number;
  color?: string;
  opacity?: number;
}) {
  const dots: React.ReactNode[] = [];
  for (let c = 0; c < cols; c++) {
    for (let rr = 0; rr < rows; rr++) {
      dots.push(
        <circle key={`${c}-${rr}`} cx={x + c * gap} cy={y + rr * gap} r={r} fill={color} />,
      );
    }
  }
  return <g opacity={opacity}>{dots}</g>;
}

/** Soft ambient colour blob. */
export function Blob({
  cx,
  cy,
  r,
  color,
  opacity = 0.14,
}: {
  cx: number;
  cy: number;
  r: number;
  color: string;
  opacity?: number;
}) {
  return <circle cx={cx} cy={cy} r={r} fill={color} opacity={opacity} />;
}

/** Generic rounded card / panel. */
export function Card({
  x,
  y,
  w,
  h,
  r = 16,
  fill = C.panel,
  stroke = C.line,
  strokeWidth = 2,
  opacity = 1,
  children,
}: {
  x: number;
  y: number;
  w: number;
  h: number;
  r?: number;
  fill?: string;
  stroke?: string;
  strokeWidth?: number;
  opacity?: number;
  children?: React.ReactNode;
}) {
  return (
    <g opacity={opacity}>
      <rect x={x} y={y} width={w} height={h} rx={r} fill={fill} stroke={stroke} strokeWidth={strokeWidth} />
      {children}
    </g>
  );
}

/** Rounded "pill" — chips, bars, progress tracks. */
export function Pill({
  x,
  y,
  w,
  h,
  fill = C.panelMute,
  opacity = 1,
}: {
  x: number;
  y: number;
  w: number;
  h: number;
  fill?: string;
  opacity?: number;
}) {
  return <rect x={x} y={y} width={w} height={h} rx={h / 2} fill={fill} opacity={opacity} />;
}

/** A lucide glyph positioned by its centre. */
export function IconGlyph({
  cx,
  cy,
  size,
  icon: Icon,
  color = C.ink,
  strokeWidth = 2,
}: {
  cx: number;
  cy: number;
  size: number;
  icon: LucideIcon;
  color?: string;
  strokeWidth?: number;
}) {
  return (
    <g transform={`translate(${cx - size / 2} ${cy - size / 2})`}>
      <Icon width={size} height={size} color={color} strokeWidth={strokeWidth} />
    </g>
  );
}

/** Circular icon badge — filled disc with a centred glyph. */
export function IconBadge({
  cx,
  cy,
  r,
  bg = C.orange,
  icon,
  color = C.white,
  iconScale = 1.05,
  strokeWidth = 2,
}: {
  cx: number;
  cy: number;
  r: number;
  bg?: string;
  icon: LucideIcon;
  color?: string;
  iconScale?: number;
  strokeWidth?: number;
}) {
  return (
    <g>
      <circle cx={cx} cy={cy} r={r} fill={bg} />
      <IconGlyph cx={cx} cy={cy} size={r * iconScale} icon={icon} color={color} strokeWidth={strokeWidth} />
    </g>
  );
}

/** Rounded-rect icon tile (app/feature tiles). */
export function IconTile({
  x,
  y,
  size,
  r = 14,
  bg = C.orangeTint,
  icon,
  color = C.orange,
  iconScale = 0.55,
  strokeWidth = 2.2,
}: {
  x: number;
  y: number;
  size: number;
  r?: number;
  bg?: string;
  icon: LucideIcon;
  color?: string;
  iconScale?: number;
  strokeWidth?: number;
}) {
  return (
    <g>
      <rect x={x} y={y} width={size} height={size} rx={r} fill={bg} />
      <IconGlyph cx={x + size / 2} cy={y + size / 2} size={size * iconScale} icon={icon} color={color} strokeWidth={strokeWidth} />
    </g>
  );
}

/** App / browser window with a header bar + traffic dots. */
export function AppWindow({
  x,
  y,
  w,
  h,
  r = 18,
  title,
  accent = C.orange,
  children,
}: {
  x: number;
  y: number;
  w: number;
  h: number;
  r?: number;
  title?: string;
  accent?: string;
  children?: React.ReactNode;
}) {
  const barH = 34;
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={r} fill={C.panel} stroke={C.line} strokeWidth={2} />
      {/* header bar */}
      <path
        d={`M${x} ${y + r} a${r} ${r} 0 0 1 ${r} ${-r} h${w - 2 * r} a${r} ${r} 0 0 1 ${r} ${r} v${barH - r} h${-w} z`}
        fill={C.panelSoft}
      />
      <line x1={x} y1={y + barH} x2={x + w} y2={y + barH} stroke={C.line} strokeWidth={2} />
      <circle cx={x + 20} cy={y + barH / 2} r={4} fill={C.red} opacity={0.8} />
      <circle cx={x + 36} cy={y + barH / 2} r={4} fill={C.gold} opacity={0.85} />
      <circle cx={x + 52} cy={y + barH / 2} r={4} fill={C.green} opacity={0.85} />
      {title && (
        <rect x={x + w / 2 - 70} y={y + barH / 2 - 7} width={140} height={14} rx={7} fill={C.panelMute} />
      )}
      <circle cx={x + w - 22} cy={y + barH / 2} r={5} fill={accent} opacity={0.9} />
      {children}
    </g>
  );
}

/** Phone frame; children are placed over the screen area. */
export function Phone({
  x,
  y,
  w,
  h,
  r = 34,
  screen = C.panel,
  children,
}: {
  x: number;
  y: number;
  w: number;
  h: number;
  r?: number;
  screen?: string;
  children?: React.ReactNode;
}) {
  const pad = 10;
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={r} fill={C.ink} />
      <rect x={x + pad} y={y + pad} width={w - 2 * pad} height={h - 2 * pad} rx={r - 8} fill={screen} />
      {/* notch */}
      <rect x={x + w / 2 - 26} y={y + pad + 6} width={52} height={10} rx={5} fill={C.ink} />
      {children}
    </g>
  );
}

/** Upward bar chart. `values` are 0..1. */
export function BarChart({
  x,
  y,
  w,
  h,
  values,
  color = C.orange,
  track = C.panelMute,
  gap = 8,
}: {
  x: number;
  y: number;
  w: number;
  h: number;
  values: number[];
  color?: string;
  track?: string;
  gap?: number;
}) {
  const n = values.length;
  const bw = (w - gap * (n - 1)) / n;
  return (
    <g>
      {values.map((v, i) => {
        const bx = x + i * (bw + gap);
        const bh = Math.max(6, v * h);
        return (
          <g key={i}>
            <rect x={bx} y={y} width={bw} height={h} rx={Math.min(6, bw / 2)} fill={track} />
            <rect x={bx} y={y + h - bh} width={bw} height={bh} rx={Math.min(6, bw / 2)} fill={i === n - 1 ? color : (track === C.panelMute ? C.blueSoft : color)} />
          </g>
        );
      })}
    </g>
  );
}

/** Upward area + line chart. `points` are 0..1 heights, evenly spaced. */
export function LineChart({
  x,
  y,
  w,
  h,
  points,
  color = C.orange,
  fill = C.orangeTint,
  dot = true,
}: {
  x: number;
  y: number;
  w: number;
  h: number;
  points: number[];
  color?: string;
  fill?: string;
  dot?: boolean;
}) {
  const n = points.length;
  const step = w / (n - 1);
  const px = (i: number) => x + i * step;
  const py = (v: number) => y + h - v * h;
  const line = points.map((v, i) => `${i === 0 ? "M" : "L"}${px(i).toFixed(1)} ${py(v).toFixed(1)}`).join(" ");
  const area = `${line} L${px(n - 1).toFixed(1)} ${y + h} L${px(0).toFixed(1)} ${y + h} Z`;
  const last = n - 1;
  return (
    <g>
      <path d={area} fill={fill} opacity={0.7} />
      <path d={line} fill="none" stroke={color} strokeWidth={4} strokeLinecap="round" strokeLinejoin="round" />
      {dot && (
        <g>
          <circle cx={px(last)} cy={py(points[last])} r={9} fill={C.white} />
          <circle cx={px(last)} cy={py(points[last])} r={6} fill={color} />
        </g>
      )}
    </g>
  );
}

/** Donut chart. `segments` are {value 0..1, color}; should sum to ~1. */
export function Donut({
  cx,
  cy,
  r,
  thickness = 18,
  segments,
  track = C.panelMute,
}: {
  cx: number;
  cy: number;
  r: number;
  thickness?: number;
  segments: { value: number; color: string }[];
  track?: string;
}) {
  const circ = 2 * Math.PI * r;
  const lens = segments.map((s) => s.value * circ);
  // Cumulative start offset for each segment — computed purely (no mutation).
  const offsets = lens.map((_, i) => lens.slice(0, i).reduce((a, b) => a + b, 0));
  return (
    <g transform={`rotate(-90 ${cx} ${cy})`}>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke={track} strokeWidth={thickness} />
      {segments.map((s, i) => (
        <circle
          key={i}
          cx={cx}
          cy={cy}
          r={r}
          fill="none"
          stroke={s.color}
          strokeWidth={thickness}
          strokeDasharray={`${lens[i]} ${circ - lens[i]}`}
          strokeDashoffset={-offsets[i]}
          strokeLinecap="round"
        />
      ))}
    </g>
  );
}

/** Stacked list rows — leading dot/avatar, two text bars, optional trailing tag. */
export function ListRows({
  x,
  y,
  w,
  rows,
  rowH = 46,
  gap = 12,
  lead = C.blueSoft,
  tag,
}: {
  x: number;
  y: number;
  w: number;
  rows: number;
  rowH?: number;
  gap?: number;
  lead?: string;
  tag?: string;
}) {
  const items: React.ReactNode[] = [];
  for (let i = 0; i < rows; i++) {
    const ry = y + i * (rowH + gap);
    items.push(
      <g key={i}>
        <rect x={x} y={ry} width={w} height={rowH} rx={12} fill={C.panel} stroke={C.lineSoft} strokeWidth={2} />
        <circle cx={x + rowH / 2} cy={ry + rowH / 2} r={rowH / 2 - 10} fill={lead} />
        <rect x={x + rowH} y={ry + 12} width={w * 0.42} height={8} rx={4} fill={C.panelMute} />
        <rect x={x + rowH} y={ry + 26} width={w * 0.26} height={7} rx={3.5} fill={C.lineSoft} />
        {tag && <rect x={x + w - 64} y={ry + rowH / 2 - 9} width={48} height={18} rx={9} fill={i === 0 ? C.greenSoft : C.panelMute} />}
      </g>,
    );
  }
  return <g>{items}</g>;
}

/** Flat upper-body person (African skin tones). Optional embedded glyph
 *  (e.g. headset, stethoscope) drawn near the head, and a tab name bar. */
export function Person({
  cx,
  topY,
  scale = 1,
  skin = C.skin2,
  shirt = C.blue,
  hair = C.hair,
  accessory,
}: {
  cx: number;
  topY: number;
  scale?: number;
  skin?: string;
  shirt?: string;
  hair?: string;
  accessory?: React.ReactNode;
}) {
  const headR = 46 * scale;
  const headCy = topY + headR + 8 * scale;
  const shoulderY = headCy + headR + 14 * scale;
  const shoulderW = 150 * scale;
  return (
    <g>
      {/* shoulders / torso */}
      <path
        d={`M${cx - shoulderW / 2} ${shoulderY + 90 * scale}
            q0 ${-90 * scale} ${shoulderW / 2} ${-90 * scale}
            q${shoulderW / 2} 0 ${shoulderW / 2} ${90 * scale} Z`}
        fill={shirt}
      />
      {/* neck */}
      <rect x={cx - 16 * scale} y={headCy + headR - 12 * scale} width={32 * scale} height={34 * scale} rx={14 * scale} fill={skin} />
      {/* head */}
      <circle cx={cx} cy={headCy} r={headR} fill={skin} />
      {/* hair cap */}
      <path
        d={`M${cx - headR} ${headCy} a${headR} ${headR} 0 0 1 ${headR * 2} 0 q${-headR} ${-30 * scale} ${-headR * 2} 0 Z`}
        fill={hair}
      />
      {accessory}
    </g>
  );
}

/** Small map pin. */
export function Pin({
  cx,
  cy,
  size = 34,
  color = C.orange,
}: {
  cx: number;
  cy: number;
  size?: number;
  color?: string;
}) {
  const w = size;
  return (
    <g>
      <path
        d={`M${cx} ${cy} c${-w * 0.55} ${-w * 0.55} ${-w * 0.55} ${-w * 1.25} 0 ${-w * 1.25} c${w * 0.55} 0 ${w * 0.55} ${w * 0.7} 0 ${w * 1.25} Z`}
        fill={color}
      />
      <circle cx={cx} cy={cy - w * 0.78} r={w * 0.2} fill={C.white} />
    </g>
  );
}

/** Dashed route between two points (logistics/delivery). */
export function Route({
  d,
  color = C.blue,
  width = 4,
}: {
  d: string;
  color?: string;
  width?: number;
}) {
  return <path d={d} fill="none" stroke={color} strokeWidth={width} strokeDasharray="2 12" strokeLinecap="round" />;
}
