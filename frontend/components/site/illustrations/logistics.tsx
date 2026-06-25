/**
 * Logistics / business-infrastructure illustrations (ABAQWA).
 * Matches the payments.tsx style: flat product-mockup look, orange #FF6B00 +
 * Quata blue, neutral surfaces, embedded lucide glyphs, African subjects.
 *
 * All landscape arts use a 4:3 viewBox (1200 x 900).
 */
import * as React from "react";
import {
  Package,
  Boxes,
  Receipt,
  BarChart3,
  Settings,
  TrendingUp,
  Store,
  Warehouse,
  Navigation,
} from "lucide-react";
import { C } from "./palette";
import {
  Card,
  Pill,
  IconBadge,
  IconTile,
  IconGlyph,
  AppWindow,
  BarChart,
  Donut,
  ListRows,
  Person,
  Pin,
  Route,
  Dots,
  Blob,
} from "./kit";

const VB = "0 0 1200 900";

/** ABAQWA hero — business-operations dashboard: KPIs, charts, inventory. */
export function BusinessOps() {
  return (
    <svg viewBox={VB} width="100%" height="100%" preserveAspectRatio="xMidYMid meet" aria-hidden role="presentation">
      <rect x={0} y={0} width={1200} height={900} fill={C.orangeTint} />
      <Blob cx={210} cy={200} r={300} color={C.orangeSoft} opacity={0.55} />
      <Blob cx={1010} cy={760} r={300} color={C.blueSoft} opacity={0.7} />
      <Dots x={80} y={730} cols={10} rows={3} color={C.orange} opacity={0.16} />

      {/* Main dashboard window */}
      <AppWindow x={80} y={90} w={1040} h={720} r={20} title="ABAQWA" accent={C.orange}>
        {/* sidebar */}
        <rect x={80} y={124} width={150} height={686} fill={C.panelSoft} />
        <line x1={230} y1={124} x2={230} y2={810} stroke={C.line} strokeWidth={2} />
        <IconTile x={110} y={156} size={48} bg={C.orange} icon={Store} color={C.white} iconScale={0.56} />
        {[Package, Receipt, BarChart3, Settings].map((Ic, i) => (
          <IconTile
            key={i}
            x={110}
            y={232 + i * 70}
            size={48}
            bg={i === 0 ? C.orangeTint : C.blueTint}
            icon={Ic}
            color={i === 0 ? C.orange : C.blue}
            iconScale={0.52}
          />
        ))}

        {/* header */}
        <text x={262} y={172} fontFamily="system-ui, sans-serif" fontSize={28} fill={C.ink} fontWeight={800}>
          Business overview
        </text>
        <text x={262} y={200} fontFamily="system-ui, sans-serif" fontSize={17} fill={C.slate}>
          POS · inventory · analytics · Bamenda
        </text>
        <Pill x={930} y={150} w={150} h={32} fill={C.blueTint} />
        <text x={952} y={172} fontFamily="system-ui, sans-serif" fontSize={16} fill={C.blue} fontWeight={700}>
          This month
        </text>

        {/* KPI stat cards */}
        <Card x={262} y={228} w={250} h={120} r={16} fill={C.panel}>
          <IconBadge cx={302} cy={272} r={22} bg={C.orangeTint} icon={Receipt} color={C.orange} iconScale={0.9} />
          <text x={336} y={266} fontFamily="system-ui, sans-serif" fontSize={15} fill={C.slate} fontWeight={600}>
            Revenue
          </text>
          <text x={336} y={296} fontFamily="system-ui, sans-serif" fontSize={26} fill={C.ink} fontWeight={800}>
            XAF 1.2M
          </text>
          <g transform="translate(286 312)"><TrendingUp width={18} height={18} color={C.green} strokeWidth={2.6} /></g>
          <text x={312} y={326} fontFamily="system-ui, sans-serif" fontSize={15} fill={C.green} fontWeight={700}>
            +18%
          </text>
        </Card>

        <Card x={530} y={228} w={250} h={120} r={16} fill={C.panel}>
          <IconBadge cx={570} cy={272} r={22} bg={C.blueTint} icon={Package} color={C.blue} iconScale={0.9} />
          <text x={604} y={266} fontFamily="system-ui, sans-serif" fontSize={15} fill={C.slate} fontWeight={600}>
            Orders
          </text>
          <text x={604} y={296} fontFamily="system-ui, sans-serif" fontSize={26} fill={C.ink} fontWeight={800}>
            1,480
          </text>
          <g transform="translate(554 312)"><TrendingUp width={18} height={18} color={C.green} strokeWidth={2.6} /></g>
          <text x={580} y={326} fontFamily="system-ui, sans-serif" fontSize={15} fill={C.green} fontWeight={700}>
            +9%
          </text>
        </Card>

        <Card x={798} y={228} w={282} h={120} r={16} fill={C.navy} stroke={C.navy}>
          <IconBadge cx={840} cy={272} r={22} bg={C.orange} icon={Boxes} color={C.white} iconScale={0.9} />
          <text x={876} y={266} fontFamily="system-ui, sans-serif" fontSize={15} fill={C.blueSky} fontWeight={600}>
            SKUs in stock
          </text>
          <text x={876} y={296} fontFamily="system-ui, sans-serif" fontSize={26} fill={C.white} fontWeight={800}>
            642
          </text>
          <text x={876} y={326} fontFamily="system-ui, sans-serif" fontSize={15} fill={C.blueLight} fontWeight={700}>
            12 low stock
          </text>
        </Card>

        {/* Sales bar chart */}
        <Card x={262} y={372} w={420} h={224} r={16} fill={C.panel}>
          <text x={288} y={408} fontFamily="system-ui, sans-serif" fontSize={18} fill={C.ink} fontWeight={700}>
            Weekly sales
          </text>
          <text x={288} y={432} fontFamily="system-ui, sans-serif" fontSize={15} fill={C.slate}>
            XAF, last 7 days
          </text>
          <BarChart x={288} y={452} w={368} h={120} values={[0.4, 0.55, 0.47, 0.7, 0.6, 0.82, 1]} color={C.orange} />
        </Card>

        {/* Channel donut */}
        <Card x={700} y={372} w={380} h={224} r={16} fill={C.panel}>
          <text x={726} y={408} fontFamily="system-ui, sans-serif" fontSize={18} fill={C.ink} fontWeight={700}>
            Sales by channel
          </text>
          <Donut
            cx={796}
            cy={510}
            r={58}
            thickness={20}
            segments={[
              { value: 0.52, color: C.orange },
              { value: 0.31, color: C.blue },
              { value: 0.17, color: C.gold },
            ]}
          />
          <text x={796} y={504} fontFamily="system-ui, sans-serif" fontSize={20} fill={C.ink} fontWeight={800} textAnchor="middle">
            642
          </text>
          <text x={796} y={524} fontFamily="system-ui, sans-serif" fontSize={12} fill={C.slate} textAnchor="middle">
            orders
          </text>
          {[
            { c: C.orange, l: "POS counter" },
            { c: C.blue, l: "Online" },
            { c: C.gold, l: "Delivery" },
          ].map((s, i) => (
            <g key={i}>
              <circle cx={904} cy={468 + i * 32} r={6} fill={s.c} />
              <text x={920} y={473 + i * 32} fontFamily="system-ui, sans-serif" fontSize={15} fill={C.slate} fontWeight={600}>
                {s.l}
              </text>
            </g>
          ))}
        </Card>

        {/* Inventory list */}
        <Card x={262} y={616} w={520} h={172} r={16} fill={C.panel}>
          <text x={288} y={650} fontFamily="system-ui, sans-serif" fontSize={18} fill={C.ink} fontWeight={700}>
            Inventory
          </text>
          <text x={672} y={650} fontFamily="system-ui, sans-serif" fontSize={14} fill={C.slate} fontWeight={600}>
            stock
          </text>
          <ListRows x={288} y={664} w={470} rows={2} rowH={46} gap={10} lead={C.orangeSoft} tag="stock" />
        </Card>

        {/* Inventory tag column accents over list rows */}
        <text x={262 + 520 - 96} y={616 + 80} fontFamily="system-ui, sans-serif" fontSize={13} fill={C.green} fontWeight={700}>
          In stock
        </text>
        <text x={262 + 520 - 96} y={616 + 136} fontFamily="system-ui, sans-serif" fontSize={13} fill={C.slate} fontWeight={700}>
          Reorder
        </text>

        {/* Quick action tiles row */}
        <Card x={800} y={616} w={280} h={172} r={16} fill={C.panelSoft} stroke={C.line}>
          <text x={826} y={650} fontFamily="system-ui, sans-serif" fontSize={18} fill={C.ink} fontWeight={700}>
            Tools
          </text>
          <IconTile x={826} y={668} size={52} bg={C.orangeTint} icon={Package} color={C.orange} iconScale={0.5} />
          <IconTile x={888} y={668} size={52} bg={C.blueTint} icon={Receipt} color={C.blue} iconScale={0.5} />
          <IconTile x={950} y={668} size={52} bg={C.orangeTint} icon={BarChart3} color={C.orange} iconScale={0.5} />
          <IconTile x={1012} y={668} size={52} bg={C.blueTint} icon={Settings} color={C.blue} iconScale={0.5} />
          <Pill x={826} y={736} w={238} h={30} fill={C.orange} />
          <text x={945} y={756} fontFamily="system-ui, sans-serif" fontSize={15} fill={C.white} fontWeight={700} textAnchor="middle">
            New order
          </text>
        </Card>
      </AppWindow>
    </svg>
  );
}

/** ABAQWA delivery / partner service hero — African rider on a scooter,
 *  dashed route between two pins, "On the way" status card. */
export function DeliveryRider() {
  return (
    <svg viewBox={VB} width="100%" height="100%" preserveAspectRatio="xMidYMid meet" aria-hidden role="presentation">
      <rect x={0} y={0} width={1200} height={900} fill={C.blueTint} />
      <Blob cx={250} cy={210} r={300} color={C.orangeSoft} opacity={0.5} />
      <Blob cx={1000} cy={730} r={300} color={C.blueSoft} opacity={0.7} />
      <Dots x={80} y={120} cols={6} rows={4} color={C.blue} opacity={0.16} />

      {/* Route from shop pin to home pin */}
      <Route d="M210 250 C 420 150, 540 360, 760 300 S 1010 460, 1010 660" color={C.blue} width={5} />
      <g transform="translate(176 240)"><Warehouse width={30} height={30} color={C.navy} strokeWidth={2.2} /></g>
      <Pin cx={210} cy={250} size={40} color={C.blue} />
      <text x={150} y={300} fontFamily="system-ui, sans-serif" fontSize={17} fill={C.navy} fontWeight={700}>
        Warehouse
      </text>
      <Pin cx={1010} cy={665} size={44} color={C.orange} />
      <text x={970} y={712} fontFamily="system-ui, sans-serif" fontSize={17} fill={C.orangeDark} fontWeight={700}>
        Bamenda
      </text>

      {/* Ground line */}
      <rect x={120} y={742} width={760} height={8} rx={4} fill={C.blueSoft} />

      {/* Scooter + rider, centred lower-left */}
      <g transform="translate(300 470)">
        {/* wheels */}
        <circle cx={40} cy={270} r={60} fill={C.ink} />
        <circle cx={40} cy={270} r={34} fill={C.panelSoft} />
        <circle cx={40} cy={270} r={12} fill={C.steel} />
        <circle cx={360} cy={270} r={60} fill={C.ink} />
        <circle cx={360} cy={270} r={34} fill={C.panelSoft} />
        <circle cx={360} cy={270} r={12} fill={C.steel} />

        {/* scooter body (orange) */}
        <path
          d="M40 270 L120 270 Q150 270 165 240 L250 240 L300 200 L344 200 Q372 200 360 250 L360 270 Z"
          fill={C.orange}
        />
        <path
          d="M40 270 L120 270 Q150 270 165 240 L250 240 L300 200 L344 200 Q372 200 360 250 L360 270 Z"
          fill="none"
          stroke={C.orangeDark}
          strokeWidth={3}
        />
        {/* floorboard + front shield */}
        <rect x={150} y={244} width={120} height={20} rx={8} fill={C.orangeDark} />
        <path d="M300 200 L312 120 Q316 108 328 108 L344 108 L344 200 Z" fill={C.navy} />
        {/* handlebar */}
        <rect x={316} y={104} width={70} height={12} rx={6} fill={C.ink} />
        {/* seat */}
        <rect x={120} y={222} width={120} height={22} rx={11} fill={C.ink} />
        {/* headlight */}
        <circle cx={350} cy={150} r={10} fill={C.gold} />

        {/* Parcel box on rear rack */}
        <rect x={6} y={150} width={120} height={96} rx={12} fill={C.blue} />
        <rect x={6} y={150} width={120} height={96} rx={12} fill="none" stroke={C.navy} strokeWidth={3} />
        <rect x={6} y={150} width={120} height={26} rx={10} fill={C.navy} />
        <g transform="translate(36 178)"><Package width={60} height={60} color={C.white} strokeWidth={2.2} /></g>

        {/* Rider */}
        <g transform="translate(190 -30)">
          <Person cx={0} topY={0} scale={0.92} skin={C.skin2} shirt={C.orange} hair={C.hair} />
          {/* helmet hint over hair */}
          <path
            d={`M${-44} ${52} a44 44 0 0 1 88 0 q-44 -22 -88 0 Z`}
            fill={C.navy}
          />
          <rect x={-46} y={50} width={92} height={10} rx={5} fill={C.navyDeep} />
          {/* visor */}
          <rect x={-30} y={62} width={56} height={16} rx={8} fill={C.blueLight} opacity={0.85} />
        </g>
      </g>

      {/* "On the way" status card */}
      <Card x={740} y={150} w={400} h={170} r={22}>
        <IconBadge cx={800} cy={222} r={34} bg={C.orange} icon={Navigation} iconScale={0.95} />
        <text x={852} y={208} fontFamily="system-ui, sans-serif" fontSize={24} fill={C.ink} fontWeight={800}>
          On the way
        </text>
        <text x={852} y={240} fontFamily="system-ui, sans-serif" fontSize={17} fill={C.slate}>
          Order #2840 · arriving 12 min
        </text>
        <Pill x={852} y={258} w={244} h={14} fill={C.orangeSoft} />
        <rect x={852} y={258} width={170} height={14} rx={7} fill={C.orange} />
        <text x={764} y={300} fontFamily="system-ui, sans-serif" fontSize={15} fill={C.slate} fontWeight={600}>
          Rider · Bamenda
        </text>
        <g transform="translate(1086 290)"><Store width={22} height={22} color={C.blue} strokeWidth={2.2} /></g>
      </Card>

      {/* Delivery stat chip */}
      <Card x={740} y={344} w={400} h={120} r={22} fill={C.navy} stroke={C.navy}>
        <IconBadge cx={800} cy={404} r={30} bg={C.orange} icon={Package} iconScale={0.95} />
        <text x={848} y={392} fontFamily="system-ui, sans-serif" fontSize={20} fill={C.white} fontWeight={700}>
          Same-day delivery
        </text>
        <text x={848} y={424} fontFamily="system-ui, sans-serif" fontSize={16} fill={C.blueSky}>
          Tracked from shop to door
        </text>
        <IconGlyph cx={1100} cy={404} size={26} icon={TrendingUp} color={C.green} strokeWidth={2.6} />
      </Card>

      <Dots x={1000} y={150} cols={5} rows={3} color={C.orange} opacity={0.18} />
    </svg>
  );
}
