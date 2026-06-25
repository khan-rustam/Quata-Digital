/**
 * Editorial illustrations — blog / news post covers.
 * Style reference: payments.tsx (flat product-mockup, orange #FF6B00 + Quata
 * blue, neutral surfaces, embedded lucide glyphs). Each category maps to a
 * distinct theme so the set reads as one cohesive family of covers.
 *
 * Cover art is 16:9 (1200 x 675) and uses preserveAspectRatio "slice" so it
 * fills any container (including fixed-height cards) behind a category pill.
 */
import * as React from "react";
import type { LucideIcon } from "lucide-react";
import {
  Layers,
  Building2,
  Lightbulb,
  Code2,
  CreditCard,
  ShoppingBag,
  Truck,
  Newspaper,
  ArrowUpRight,
  Sparkles,
} from "lucide-react";
import { C } from "./palette";
import { Card, Pill, IconBadge, IconTile, BarChart, LineChart, Dots, Blob } from "./kit";

const W = 1200;
const H = 675;

type Theme = {
  bg: string;
  bgBlob: string;
  accent: string;
  accentDark: string;
  accentSoft: string;
  accentTint: string;
  icon: LucideIcon;
  word: string;
};

const THEMES: Record<string, Theme> = {
  product: {
    bg: C.blueTint,
    bgBlob: C.blueSoft,
    accent: C.blue,
    accentDark: C.navy,
    accentSoft: C.blueSoft,
    accentTint: C.blueTint,
    icon: Layers,
    word: "Product",
  },
  company: {
    bg: C.orangeTint,
    bgBlob: C.orangeSoft,
    accent: C.orange,
    accentDark: C.orangeDark,
    accentSoft: C.orangeSoft,
    accentTint: C.orangeTint,
    icon: Building2,
    word: "Company",
  },
  insight: {
    bg: C.blueTint,
    bgBlob: C.blueSoft,
    accent: C.navy,
    accentDark: C.navyDeep,
    accentSoft: C.blueSoft,
    accentTint: C.blueTint,
    icon: Lightbulb,
    word: "Insight",
  },
  engineering: {
    bg: C.blueTint,
    bgBlob: C.blueSoft,
    accent: C.blue,
    accentDark: C.navy,
    accentSoft: C.blueSoft,
    accentTint: C.blueTint,
    icon: Code2,
    word: "Engineering",
  },
  payments: {
    bg: C.orangeTint,
    bgBlob: C.orangeSoft,
    accent: C.orange,
    accentDark: C.orangeDark,
    accentSoft: C.orangeSoft,
    accentTint: C.orangeTint,
    icon: CreditCard,
    word: "Payments",
  },
  commerce: {
    bg: C.orangeTint,
    bgBlob: C.orangeSoft,
    accent: C.orange,
    accentDark: C.orangeDark,
    accentSoft: C.orangeSoft,
    accentTint: C.orangeTint,
    icon: ShoppingBag,
    word: "Commerce",
  },
  logistics: {
    bg: C.blueTint,
    bgBlob: C.blueSoft,
    accent: C.blue,
    accentDark: C.navy,
    accentSoft: C.blueSoft,
    accentTint: C.blueTint,
    icon: Truck,
    word: "Logistics",
  },
};

const DEFAULT_THEME: Theme = {
  bg: C.orangeTint,
  bgBlob: C.orangeSoft,
  accent: C.orange,
  accentDark: C.orangeDark,
  accentSoft: C.orangeSoft,
  accentTint: C.orangeTint,
  icon: Newspaper,
  word: "Insights",
};

/** Blog / news post cover — themed per category, sits behind a category pill. */
export function PostCover({ category }: { category?: string }) {
  const t = THEMES[(category ?? "").trim().toLowerCase()] ?? DEFAULT_THEME;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="100%" preserveAspectRatio="xMidYMid slice" aria-hidden role="presentation">
      <rect x={0} y={0} width={W} height={H} fill={t.bg} />

      {/* Ambient texture */}
      <Blob cx={210} cy={140} r={300} color={t.bgBlob} opacity={0.7} />
      <Blob cx={1080} cy={620} r={320} color={t.accentSoft} opacity={0.6} />
      <Blob cx={980} cy={120} r={150} color={C.orangeSoft} opacity={0.35} />
      <Dots x={70} y={470} cols={9} rows={4} color={t.accent} opacity={0.16} />
      <Dots x={1010} y={70} cols={4} rows={4} color={t.accentDark} opacity={0.12} />

      {/* Hero icon badge + topic word */}
      <IconBadge cx={210} cy={300} r={92} bg={t.accent} icon={t.icon} color={C.white} iconScale={0.92} strokeWidth={2.2} />
      <g transform="translate(176 290)"><Sparkles width={26} height={26} color={t.accentDark} strokeWidth={2.4} /></g>

      <text x={350} y={290} fontFamily="system-ui, sans-serif" fontSize={26} fill={t.accentDark} fontWeight={700} letterSpacing={3}>
        QUATA DIGITAL
      </text>
      <text x={350} y={372} fontFamily="system-ui, sans-serif" fontSize={88} fill={C.ink} fontWeight={800}>
        {t.word}
      </text>
      <Pill x={352} y={404} w={220} h={14} fill={t.accentSoft} />

      {/* Category tag chip */}
      <g>
        <rect x={352} y={206} width={20} height={20} rx={5} fill={t.accent} />
        <text x={384} y={222} fontFamily="system-ui, sans-serif" fontSize={20} fill={C.slate} fontWeight={600}>
          Bamenda · {t.word.toLowerCase()}
        </text>
      </g>

      {/* Decorative metric card — top right */}
      <Card x={832} y={120} w={300} h={172} r={22}>
        <IconTile x={858} y={146} size={50} bg={t.accentTint} icon={ArrowUpRight} color={t.accent} iconScale={0.56} strokeWidth={2.4} />
        <text x={924} y={166} fontFamily="system-ui, sans-serif" fontSize={18} fill={C.slate} fontWeight={600}>This week</text>
        <text x={924} y={196} fontFamily="system-ui, sans-serif" fontSize={28} fill={C.ink} fontWeight={800}>+24%</text>
        <BarChart x={858} y={216} w={250} h={56} values={[0.4, 0.55, 0.48, 0.7, 0.62, 0.85, 1]} color={t.accent} />
      </Card>

      {/* Decorative trend card — bottom right */}
      <Card x={832} y={330} w={300} h={250} r={22}>
        <text x={858} y={372} fontFamily="system-ui, sans-serif" fontSize={18} fill={C.slate} fontWeight={600}>Read momentum</text>
        <text x={858} y={406} fontFamily="system-ui, sans-serif" fontSize={26} fill={t.accentDark} fontWeight={800}>XAF 1.2M</text>
        <LineChart
          x={858}
          y={430}
          w={250}
          h={120}
          points={[0.25, 0.4, 0.32, 0.55, 0.5, 0.74, 0.92]}
          color={t.accent}
          fill={t.accentTint}
        />
      </Card>

      {/* Article snippet card — bottom left */}
      <Card x={70} y={470} w={520} h={140} r={22}>
        <IconBadge cx={134} cy={540} r={38} bg={t.accentTint} icon={t.icon} color={t.accent} iconScale={0.92} />
        <rect x={194} y={502} width={300} height={14} rx={7} fill={C.panelMute} />
        <rect x={194} y={530} width={240} height={11} rx={5.5} fill={C.lineSoft} />
        <Pill x={194} y={556} w={120} h={26} fill={t.accentSoft} />
        <rect x={326} y={556} width={90} height={26} rx={13} fill={C.panelMute} />
      </Card>
    </svg>
  );
}
