/**
 * Analytics illustrations (investor growth metrics + analytics dashboards).
 * Style reference: payments.tsx — flat product-mockup look, orange #FF6B00 +
 * Quata blue, neutral surfaces, embedded lucide glyphs.
 *
 * All landscape arts use a 4:3 viewBox (1200 x 900).
 */
import * as React from "react";
import {
  ArrowUpRight,
  TrendingUp,
  Users,
  BarChart3,
  PieChart,
  Activity,
  Globe2,
} from "lucide-react";
import { C } from "./palette";
import { Card, Pill, IconBadge, IconTile, AppWindow, BarChart, LineChart, Donut, Dots, Blob, Pin } from "./kit";

const VB = "0 0 1200 900";

/** Investor hero — growth dashboard: trending LineChart, KPI cards, BarChart, market map. */
export function GrowthCharts() {
  return (
    <svg viewBox={VB} width="100%" height="100%" preserveAspectRatio="xMidYMid meet" aria-hidden role="presentation">
      <rect x={0} y={0} width={1200} height={900} fill={C.blueTint} />
      <Blob cx={260} cy={200} r={300} color={C.orangeSoft} opacity={0.5} />
      <Blob cx={1010} cy={760} r={300} color={C.blueSoft} opacity={0.7} />
      <Dots x={70} y={650} cols={9} rows={5} color={C.blue} opacity={0.16} />

      {/* Title strip */}
      <IconBadge cx={108} cy={108} r={34} bg={C.orange} icon={TrendingUp} iconScale={1.0} />
      <text x={158} y={102} fontFamily="system-ui, sans-serif" fontSize={32} fill={C.ink} fontWeight={800}>Growth metrics</text>
      <text x={158} y={134} fontFamily="system-ui, sans-serif" fontSize={20} fill={C.slate}>Fintech expansion · Bamenda &amp; beyond</text>

      {/* Main dashboard window */}
      <AppWindow x={70} y={180} w={760} h={650} title="dashboard" accent={C.orange}>
        {/* Revenue growth headline + line chart */}
        <text x={104} y={258} fontFamily="system-ui, sans-serif" fontSize={20} fill={C.slate} fontWeight={600}>Gross merchandise value</text>
        <text x={104} y={304} fontFamily="system-ui, sans-serif" fontSize={42} fill={C.ink} fontWeight={800}>XAF 4.2B</text>
        <g transform="translate(300 278)"><ArrowUpRight width={26} height={26} color={C.green} strokeWidth={2.8} /></g>
        <text x={330} y={300} fontFamily="system-ui, sans-serif" fontSize={26} fill={C.green} fontWeight={800}>+altMoM</text>

        <LineChart
          x={104}
          y={330}
          w={692}
          h={250}
          points={[0.18, 0.26, 0.22, 0.4, 0.46, 0.6, 0.7, 0.86, 1.0]}
          color={C.orange}
          fill={C.orangeTint}
        />

        {/* Bottom bar chart panel */}
        <Card x={104} y={612} w={330} h={190} r={16} fill={C.panelSoft} stroke={C.line}>
          <text x={128} y={648} fontFamily="system-ui, sans-serif" fontSize={18} fill={C.slate} fontWeight={600}>Monthly volume</text>
          <g transform="translate(380 632)"><BarChart3 width={22} height={22} color={C.blue} strokeWidth={2.4} /></g>
          <BarChart x={128} y={668} w={282} h={116} values={[0.4, 0.52, 0.46, 0.68, 0.62, 0.82, 1]} color={C.blue} track={C.blueSoft} />
        </Card>

        {/* Market opportunity card */}
        <Card x={454} y={612} w={342} h={190} r={16} fill={C.navy} stroke={C.navy}>
          <text x={478} y={648} fontFamily="system-ui, sans-serif" fontSize={18} fill={C.blueSky} fontWeight={600}>Market opportunity</text>
          <text x={478} y={694} fontFamily="system-ui, sans-serif" fontSize={36} fill={C.white} fontWeight={800}>XAF 18B</text>
          <text x={478} y={726} fontFamily="system-ui, sans-serif" fontSize={16} fill={C.blueSoft}>Addressable CEMAC market</text>
          {/* mini market map */}
          <rect x={478} y={744} width={290} height={40} rx={10} fill={C.navyDeep} />
          <Pin cx={520} cy={772} size={24} color={C.orange} />
          <Pin cx={600} cy={772} size={24} color={C.blueLight} />
          <Pin cx={690} cy={772} size={24} color={C.orange} />
          <g transform="translate(726 752)"><Globe2 width={28} height={28} color={C.blueSky} strokeWidth={2.2} /></g>
        </Card>
      </AppWindow>

      {/* Right KPI stat cards */}
      <Card x={860} y={180} w={270} h={200} r={20}>
        <IconBadge cx={904} cy={232} r={28} bg={C.orangeTint} icon={Activity} color={C.orange} iconScale={0.9} />
        <g transform="translate(1066 210)"><ArrowUpRight width={24} height={24} color={C.green} strokeWidth={2.8} /></g>
        <text x={886} y={300} fontFamily="system-ui, sans-serif" fontSize={18} fill={C.slate} fontWeight={600}>GMV</text>
        <text x={886} y={340} fontFamily="system-ui, sans-serif" fontSize={34} fill={C.ink} fontWeight={800}>XAF 4.2B</text>
        <text x={886} y={366} fontFamily="system-ui, sans-serif" fontSize={16} fill={C.green} fontWeight={700}>+altMoM growth</text>
      </Card>

      <Card x={860} y={400} w={270} h={200} r={20}>
        <IconBadge cx={904} cy={452} r={28} bg={C.blueSoft} icon={Users} color={C.blue} iconScale={0.9} />
        <g transform="translate(1066 430)"><ArrowUpRight width={24} height={24} color={C.green} strokeWidth={2.8} /></g>
        <text x={886} y={520} fontFamily="system-ui, sans-serif" fontSize={18} fill={C.slate} fontWeight={600}>Active users</text>
        <text x={886} y={560} fontFamily="system-ui, sans-serif" fontSize={34} fill={C.ink} fontWeight={800}>120k</text>
        <text x={886} y={586} fontFamily="system-ui, sans-serif" fontSize={16} fill={C.green} fontWeight={700}>+altMoM growth</text>
      </Card>

      {/* TrendingUp accent card */}
      <Card x={860} y={620} w={270} h={210} r={20} fill={C.orangeTint} stroke={C.orangeSoft}>
        <g transform="translate(880 648)"><TrendingUp width={30} height={30} color={C.orange} strokeWidth={2.6} /></g>
        <text x={920} y={672} fontFamily="system-ui, sans-serif" fontSize={20} fill={C.ink} fontWeight={800}>Trajectory</text>
        <LineChart
          x={884}
          y={700}
          w={222}
          h={96}
          points={[0.2, 0.34, 0.5, 0.62, 0.8, 1.0]}
          color={C.orange}
          fill={C.orangeSoft}
          dot={false}
        />
        <Pill x={884} y={806} w={222} h={14} fill={C.orangeSoft} />
      </Card>
    </svg>
  );
}

/** Investor sidebar — laptop showing an analytics dashboard (line + donut + stat cards). */
export function AnalyticsLaptop() {
  return (
    <svg viewBox={VB} width="100%" height="100%" preserveAspectRatio="xMidYMid meet" aria-hidden role="presentation">
      <rect x={0} y={0} width={1200} height={900} fill={C.panelSoft} />
      <Blob cx={280} cy={230} r={300} color={C.blueSoft} opacity={0.7} />
      <Blob cx={960} cy={740} r={280} color={C.orangeSoft} opacity={0.5} />
      <Dots x={90} y={120} cols={6} rows={4} color={C.blue} opacity={0.14} />

      {/* Laptop lid frame */}
      <rect x={170} y={120} width={860} height={560} rx={26} fill={C.navy} />
      <rect x={170} y={120} width={860} height={560} rx={26} fill="none" stroke={C.navyDeep} strokeWidth={6} />

      {/* Screen = analytics AppWindow */}
      <AppWindow x={196} y={148} w={808} h={504} title="analytics" accent={C.orange}>
        {/* Header KPI */}
        <IconBadge cx={240} cy={222} r={26} bg={C.orange} icon={TrendingUp} iconScale={1.0} />
        <text x={282} y={214} fontFamily="system-ui, sans-serif" fontSize={22} fill={C.ink} fontWeight={800}>Performance</text>
        <text x={282} y={242} fontFamily="system-ui, sans-serif" fontSize={16} fill={C.slate}>Last 6 months · Bamenda</text>

        {/* Main line chart panel */}
        <Card x={216} y={272} w={460} h={350} r={16} fill={C.panelSoft} stroke={C.line}>
          <text x={240} y={308} fontFamily="system-ui, sans-serif" fontSize={18} fill={C.slate} fontWeight={600}>Revenue trend</text>
          <text x={240} y={344} fontFamily="system-ui, sans-serif" fontSize={30} fill={C.ink} fontWeight={800}>XAF 4.2B</text>
          <g transform="translate(410 322)"><ArrowUpRight width={22} height={22} color={C.green} strokeWidth={2.8} /></g>
          <text x={438} y={342} fontFamily="system-ui, sans-serif" fontSize={20} fill={C.green} fontWeight={800}>+28%</text>
          <LineChart
            x={240}
            y={368}
            w={412}
            h={210}
            points={[0.22, 0.32, 0.28, 0.46, 0.58, 0.74, 1.0]}
            color={C.orange}
            fill={C.orangeTint}
          />
        </Card>

        {/* Donut panel */}
        <Card x={696} y={272} w={286} h={210} r={16} fill={C.panel} stroke={C.line}>
          <text x={720} y={308} fontFamily="system-ui, sans-serif" fontSize={18} fill={C.slate} fontWeight={600}>Channel mix</text>
          <g transform="translate(706 318)"><PieChart width={20} height={20} color={C.blue} strokeWidth={2.4} /></g>
          <Donut
            cx={772}
            cy={400}
            r={56}
            thickness={20}
            segments={[
              { value: 0.52, color: C.orange },
              { value: 0.3, color: C.blue },
              { value: 0.18, color: C.blueLight },
            ]}
          />
          {/* legend */}
          <circle cx={868} cy={372} r={6} fill={C.orange} />
          <text x={884} y={378} fontFamily="system-ui, sans-serif" fontSize={15} fill={C.slate} fontWeight={600}>MoMo 52%</text>
          <circle cx={868} cy={400} r={6} fill={C.blue} />
          <text x={884} y={406} fontFamily="system-ui, sans-serif" fontSize={15} fill={C.slate} fontWeight={600}>Cards 30%</text>
          <circle cx={868} cy={428} r={6} fill={C.blueLight} />
          <text x={884} y={434} fontFamily="system-ui, sans-serif" fontSize={15} fill={C.slate} fontWeight={600}>QR 18%</text>
        </Card>

        {/* Stat card — Users */}
        <Card x={696} y={500} w={138} h={122} r={16} fill={C.blueTint} stroke={C.blueSoft}>
          <IconTile x={716} y={520} size={36} bg={C.blue} icon={Users} color={C.white} iconScale={0.56} />
          <text x={716} y={584} fontFamily="system-ui, sans-serif" fontSize={26} fill={C.ink} fontWeight={800}>120k</text>
          <text x={716} y={608} fontFamily="system-ui, sans-serif" fontSize={14} fill={C.slate} fontWeight={600}>Active users</text>
        </Card>

        {/* Stat card — Growth */}
        <Card x={844} y={500} w={138} h={122} r={16} fill={C.orangeTint} stroke={C.orangeSoft}>
          <IconTile x={864} y={520} size={36} bg={C.orange} icon={ArrowUpRight} color={C.white} iconScale={0.56} />
          <text x={864} y={584} fontFamily="system-ui, sans-serif" fontSize={26} fill={C.ink} fontWeight={800}>+28%</text>
          <text x={864} y={608} fontFamily="system-ui, sans-serif" fontSize={14} fill={C.slate} fontWeight={600}>MoM growth</text>
        </Card>
      </AppWindow>

      {/* Laptop base / keyboard deck */}
      <path d="M120 680 h960 l60 84 q8 22 -16 22 H76 q-24 0 -16 -22 Z" fill={C.steel} />
      <path d="M120 680 h960 l60 84 q8 22 -16 22 H76 q-24 0 -16 -22 Z" fill="none" stroke={C.line} strokeWidth={2} />
      <rect x={500} y={684} width={200} height={14} rx={7} fill={C.line} />
    </svg>
  );
}
