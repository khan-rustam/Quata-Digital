/**
 * People illustrations — teams, portraits, support & boardroom scenes.
 * Style reference: payments.tsx (flat product-mockup look, orange #FF6B00 +
 * Quata blue, neutral surfaces, embedded lucide glyphs). Subjects are African
 * (skin tones C.skin1/2/3) per brand requirement.
 *
 * Landscape arts use varied viewBoxes per the spec; portraits are 900 x 1100.
 */
import * as React from "react";
import {
  Users,
  Lightbulb,
  Rocket,
  Briefcase,
  Building2,
  TrendingUp,
  Code2,
  Terminal,
  Headphones,
  MessageCircle,
  Handshake,
  Smartphone,
  Store,
  BadgeCheck,
  MapPin,
} from "lucide-react";
import { C } from "./palette";
import {
  Card,
  Pill,
  IconBadge,
  IconTile,
  AppWindow,
  BarChart,
  LineChart,
  ListRows,
  Person,
  Pin,
  Dots,
  Blob,
} from "./kit";

/* ------------------------------------------------------------------ */
/* ABOUT hero — diverse African startup team collaborating            */
/* ------------------------------------------------------------------ */
export function TeamCollab() {
  const W = 1200;
  const H = 1000;
  return (
    <svg viewBox="0 0 1200 1000" width="100%" height="100%" preserveAspectRatio="xMidYMid meet" aria-hidden role="presentation">
      <rect x={0} y={0} width={W} height={H} fill={C.orangeTint} />
      <Blob cx={250} cy={230} r={320} color={C.blueSoft} opacity={0.6} />
      <Blob cx={980} cy={820} r={320} color={C.orangeSoft} opacity={0.55} />
      <Dots x={70} y={760} cols={11} rows={4} color={C.blue} opacity={0.15} />

      {/* Whiteboard / app window with kanban behind the team */}
      <AppWindow x={320} y={90} w={560} h={300} title="Roadmap" accent={C.orange}>
        {/* kanban columns */}
        {[0, 1, 2].map((col) => (
          <g key={col}>
            <rect x={352 + col * 172} y={158} width={148} height={210} rx={12} fill={C.panelSoft} stroke={C.lineSoft} strokeWidth={2} />
            <rect x={368 + col * 172} y={174} width={70} height={10} rx={5} fill={col === 0 ? C.orange : col === 1 ? C.blue : C.green} />
            {[0, 1, 2].map((row) => (
              <rect key={row} x={368 + col * 172} y={198 + row * 52} width={116} height={36} rx={9} fill={C.panel} stroke={C.line} strokeWidth={1.6} />
            ))}
          </g>
        ))}
      </AppWindow>

      {/* Sticky notes */}
      <g transform="rotate(-6 150 250)">
        <rect x={110} y={210} width={92} height={92} rx={8} fill={C.gold} opacity={0.92} />
        <rect x={126} y={234} width={60} height={8} rx={4} fill={C.navy} opacity={0.35} />
        <rect x={126} y={252} width={44} height={8} rx={4} fill={C.navy} opacity={0.25} />
      </g>
      <g transform="rotate(7 1060 230)">
        <rect x={1010} y={200} width={92} height={92} rx={8} fill={C.blueLight} opacity={0.9} />
        <rect x={1026} y={224} width={60} height={8} rx={4} fill={C.navy} opacity={0.4} />
        <rect x={1026} y={242} width={44} height={8} rx={4} fill={C.navy} opacity={0.3} />
      </g>

      {/* Team table */}
      <rect x={150} y={690} width={900} height={150} rx={28} fill={C.navy} />
      <rect x={150} y={690} width={900} height={26} rx={13} fill={C.navyDeep} />

      {/* Three teammates around the table — varied skin tones + shirts */}
      <g transform="translate(330 470)">
        <Person cx={0} topY={0} scale={1.15} skin={C.skin1} shirt={C.orange} />
      </g>
      <g transform="translate(600 440)">
        <Person cx={0} topY={0} scale={1.25} skin={C.skin3} shirt={C.blue} />
      </g>
      <g transform="translate(870 470)">
        <Person cx={0} topY={0} scale={1.15} skin={C.skin2} shirt={C.navy} />
      </g>

      {/* Open laptops on the table */}
      {[400, 600, 800].map((lx, i) => (
        <g key={i}>
          <rect x={lx - 52} y={720} width={104} height={64} rx={8} fill={C.panel} stroke={C.line} strokeWidth={2.4} />
          <rect x={lx - 40} y={730} width={80} height={44} rx={4} fill={i === 1 ? C.blueTint : C.panelSoft} />
          <rect x={lx - 64} y={784} width={128} height={12} rx={6} fill={C.steel} />
        </g>
      ))}

      {/* Topic chips */}
      <Card x={120} y={880} w={300} h={84} r={20}>
        <IconBadge cx={170} cy={922} r={28} bg={C.orange} icon={Users} iconScale={1.0} />
        <text x={210} y={912} fontFamily="system-ui, sans-serif" fontSize={22} fill={C.ink} fontWeight={700}>One team</text>
        <text x={210} y={940} fontFamily="system-ui, sans-serif" fontSize={17} fill={C.slate}>Bamenda · remote</text>
      </Card>
      <Card x={780} y={880} w={300} h={84} r={20}>
        <IconBadge cx={830} cy={922} r={28} bg={C.blue} icon={Rocket} iconScale={1.0} />
        <text x={870} y={912} fontFamily="system-ui, sans-serif" fontSize={22} fill={C.ink} fontWeight={700}>Build fast</text>
        <text x={870} y={940} fontFamily="system-ui, sans-serif" fontSize={17} fill={C.slate}>ship · learn · iterate</text>
      </Card>

      {/* Idea badge floating */}
      <IconBadge cx={920} cy={150} r={34} bg={C.gold} icon={Lightbulb} color={C.navy} iconScale={1.0} />
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/* CAREERS hero — teammates at work, hiring chip                       */
/* ------------------------------------------------------------------ */
export function TeamCareers() {
  const W = 1200;
  const H = 1000;
  return (
    <svg viewBox="0 0 1200 1000" width="100%" height="100%" preserveAspectRatio="xMidYMid meet" aria-hidden role="presentation">
      <rect x={0} y={0} width={W} height={H} fill={C.blueTint} />
      <Blob cx={980} cy={230} r={320} color={C.orangeSoft} opacity={0.5} />
      <Blob cx={220} cy={820} r={300} color={C.blueSoft} opacity={0.7} />
      <Dots x={840} y={720} cols={9} rows={4} color={C.navy} opacity={0.14} />

      {/* Wall of sticky notes / kanban (small rects) */}
      <Card x={80} y={90} w={360} h={420} r={24} fill={C.panel}>
        <text x={116} y={148} fontFamily="system-ui, sans-serif" fontSize={22} fill={C.ink} fontWeight={800}>Sprint board</text>
        {Array.from({ length: 9 }).map((_, i) => {
          const col = i % 3;
          const row = Math.floor(i / 3);
          const colors = [C.orangeSoft, C.blueSoft, C.goldSoft];
          return (
            <g key={i}>
              <rect x={116 + col * 102} y={176 + row * 102} width={86} height={86} rx={10} fill={colors[(col + row) % 3]} />
              <rect x={130 + col * 102} y={198 + row * 102} width={52} height={8} rx={4} fill={C.navy} opacity={0.35} />
              <rect x={130 + col * 102} y={216 + row * 102} width={36} height={8} rx={4} fill={C.navy} opacity={0.25} />
            </g>
          );
        })}
      </Card>

      {/* Code window behind standing desk */}
      <AppWindow x={760} y={120} w={380} h={300} title="app.tsx" accent={C.blue}>
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <g key={i}>
            <rect x={788} y={176 + i * 36} width={14} height={14} rx={4} fill={i % 2 ? C.orange : C.blue} opacity={0.7} />
            <rect x={812} y={180 + i * 36} width={[200, 150, 230, 170, 210, 130][i]} height={9} rx={4.5} fill={i === 2 ? C.orangeSoft : C.panelMute} />
          </g>
        ))}
      </AppWindow>

      {/* Standing desk teammate with laptop */}
      <rect x={520} y={760} width={300} height={20} rx={10} fill={C.navy} />
      <rect x={555} y={780} width={18} height={170} rx={6} fill={C.navyDeep} />
      <rect x={767} y={780} width={18} height={170} rx={6} fill={C.navyDeep} />
      <g transform="translate(670 430)">
        <Person cx={0} topY={0} scale={1.2} skin={C.skin2} shirt={C.blue} />
      </g>
      <g>
        <rect x={618} y={700} width={104} height={62} rx={8} fill={C.panel} stroke={C.line} strokeWidth={2.4} />
        <rect x={630} y={710} width={80} height={42} rx={4} fill={C.blueTint} />
      </g>

      {/* Seated teammate with tablet */}
      <g transform="translate(290 560)">
        <Person cx={0} topY={0} scale={1.15} skin={C.skin1} shirt={C.orange} />
      </g>
      <g transform="rotate(-10 250 770)">
        <rect x={196} y={730} width={120} height={86} rx={12} fill={C.ink} />
        <rect x={206} y={740} width={100} height={66} rx={6} fill={C.panelSoft} />
        <rect x={216} y={752} width={56} height={9} rx={4.5} fill={C.orange} opacity={0.8} />
        <rect x={216} y={770} width={80} height={8} rx={4} fill={C.panelMute} />
        <rect x={216} y={786} width={64} height={8} rx={4} fill={C.lineSoft} />
      </g>

      {/* "We're hiring" chip */}
      <Card x={80} y={560} w={340} h={92} r={22} fill={C.navy} stroke={C.navy}>
        <IconBadge cx={132} cy={606} r={30} bg={C.orange} icon={Briefcase} iconScale={1.0} />
        <text x={178} y={596} fontFamily="system-ui, sans-serif" fontSize={24} fill={C.white} fontWeight={800}>We&apos;re hiring</text>
        <text x={178} y={628} fontFamily="system-ui, sans-serif" fontSize={18} fill={C.blueSky}>Engineering · Bamenda</text>
      </Card>

      {/* Open roles list */}
      <Card x={80} y={680} w={340} h={250} r={22}>
        <text x={116} y={720} fontFamily="system-ui, sans-serif" fontSize={20} fill={C.ink} fontWeight={700}>Open roles</text>
        <ListRows x={116} y={736} w={272} rows={3} rowH={50} gap={12} lead={C.orangeSoft} tag="new" />
      </Card>
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/* PORTRAIT helpers — vertical studio cards, 900 x 1100               */
/* ------------------------------------------------------------------ */
const PW = 900;
const PH = 1100;

/* ABOUT founder — honest stylized portrait card */
export function PortraitFounder() {
  return (
    <svg viewBox="0 0 900 1100" width="100%" height="100%" preserveAspectRatio="xMidYMid meet" aria-hidden role="presentation">
      <rect x={0} y={0} width={PW} height={PH} fill={C.panelSoft} />
      <Blob cx={210} cy={250} r={300} color={C.orangeSoft} opacity={0.4} />
      <Blob cx={720} cy={880} r={300} color={C.blueSoft} opacity={0.55} />

      {/* Studio card */}
      <Card x={120} y={120} w={660} h={860} r={36} fill={C.panel}>
        {/* portrait backdrop */}
        <rect x={160} y={160} width={580} height={520} rx={28} fill={C.navy} />
        <Blob cx={450} cy={420} r={210} color={C.blue} opacity={0.35} />
        <Dots x={210} y={210} cols={10} rows={3} color={C.blueSky} opacity={0.3} />

        {/* Flat person bust */}
        <g transform="translate(450 300)">
          <Person cx={0} topY={0} scale={1.7} skin={C.skin2} shirt={C.navy} />
        </g>

        {/* Monogram badge */}
        <circle cx={650} cy={620} r={56} fill={C.orange} />
        <text x={650} y={636} textAnchor="middle" fontFamily="system-ui, sans-serif" fontSize={38} fill={C.white} fontWeight={800}>CN</text>

        {/* Name + chips */}
        <text x={160} y={760} fontFamily="system-ui, sans-serif" fontSize={42} fill={C.ink} fontWeight={800}>Clovis Neba</text>

        <Card x={160} y={792} w={250} h={66} r={20} fill={C.orangeTint} stroke={C.orangeSoft}>
          <IconBadge cx={200} cy={825} r={22} bg={C.orange} icon={Rocket} iconScale={1.0} />
          <text x={234} y={832} fontFamily="system-ui, sans-serif" fontSize={20} fill={C.orangeDark} fontWeight={700}>Founder &amp; CEO</text>
        </Card>

        <Card x={430} y={792} w={310} h={66} r={20} fill={C.blueTint} stroke={C.blueSoft}>
          <circle cx={468} cy={825} r={12} fill={C.orange} />
          <text x={492} y={832} fontFamily="system-ui, sans-serif" fontSize={20} fill={C.navy} fontWeight={700}>QUATA DIGITAL</text>
        </Card>

        <text x={160} y={912} fontFamily="system-ui, sans-serif" fontSize={20} fill={C.slate}>Building Africa&apos;s digital backbone — from Bamenda.</text>
      </Card>
    </svg>
  );
}

/* Partner BUSINESS faq — businesswoman in her shop holding a phone */
export function PortraitBusiness() {
  return (
    <svg viewBox="0 0 900 1100" width="100%" height="100%" preserveAspectRatio="xMidYMid meet" aria-hidden role="presentation">
      <rect x={0} y={0} width={PW} height={PH} fill={C.orangeTint} />
      <Blob cx={720} cy={250} r={300} color={C.blueSoft} opacity={0.55} />
      <Blob cx={180} cy={900} r={280} color={C.orangeSoft} opacity={0.6} />

      {/* Shop awning backdrop */}
      <rect x={140} y={150} width={620} height={66} rx={14} fill={C.navy} />
      {Array.from({ length: 10 }).map((_, i) => (
        <rect key={i} x={152 + i * 60} y={150} width={30} height={66} fill={i % 2 ? C.orange : C.white} opacity={i % 2 ? 0.9 : 0.85} />
      ))}
      <text x={150} y={280} fontFamily="system-ui, sans-serif" fontSize={30} fill={C.ink} fontWeight={800}>My shop · Bamenda</text>
      <Pill x={150} y={300} w={260} h={18} fill={C.orangeSoft} />

      {/* Person */}
      <g transform="translate(420 420)">
        <Person cx={0} topY={0} scale={1.7} skin={C.skin3} shirt={C.orange} />
      </g>

      {/* Phone in hand */}
      <g transform="rotate(-8 300 760)">
        <rect x={250} y={680} width={120} height={210} rx={22} fill={C.ink} />
        <rect x={260} y={690} width={100} height={190} rx={16} fill={C.panel} />
        <rect x={272} y={712} width={76} height={40} rx={10} fill={C.navy} />
        <text x={284} y={738} fontFamily="system-ui, sans-serif" fontSize={14} fill={C.white} fontWeight={700}>XAF 12,500</text>
        {[0, 1, 2].map((i) => (
          <rect key={i} x={272} y={770 + i * 30} width={76} height={20} rx={6} fill={i === 0 ? C.greenSoft : C.panelMute} />
        ))}
      </g>

      {/* Store icon tile */}
      <IconTile x={620} y={520} size={72} bg={C.blueSoft} icon={Store} color={C.blue} iconScale={0.55} />
      <IconBadge cx={140} cy={560} r={32} bg={C.orange} icon={Smartphone} iconScale={1.0} />

      {/* Paid chip */}
      <Card x={500} y={920} w={300} h={92} r={24} fill={C.navy} stroke={C.navy}>
        <IconBadge cx={552} cy={966} r={30} bg={C.green} icon={BadgeCheck} iconScale={1.0} />
        <text x={598} y={956} fontFamily="system-ui, sans-serif" fontSize={24} fill={C.white} fontWeight={800}>Paid</text>
        <text x={598} y={988} fontFamily="system-ui, sans-serif" fontSize={18} fill={C.blueSky}>settled instantly</text>
      </Card>
    </svg>
  );
}

/* Partner STRATEGIC faq — executive in a suit, leadership pose */
export function PortraitExec() {
  return (
    <svg viewBox="0 0 900 1100" width="100%" height="100%" preserveAspectRatio="xMidYMid meet" aria-hidden role="presentation">
      <rect x={0} y={0} width={PW} height={PH} fill={C.blueTint} />
      <Blob cx={210} cy={250} r={300} color={C.blueSoft} opacity={0.7} />
      <Blob cx={720} cy={900} r={280} color={C.orangeSoft} opacity={0.45} />

      {/* Boardroom backdrop — window grid */}
      <Card x={120} y={130} w={660} h={360} r={28} fill={C.navy} stroke={C.navyDeep}>
        {Array.from({ length: 12 }).map((_, i) => (
          <rect key={i} x={160 + (i % 4) * 160} y={170 + Math.floor(i / 4) * 100} width={130} height={70} rx={10} fill={C.blue} opacity={0.4} />
        ))}
      </Card>

      {/* Person — navy suit */}
      <g transform="translate(450 380)">
        <Person cx={0} topY={0} scale={1.8} skin={C.skin1} shirt={C.navy} />
      </g>
      {/* Tie hint + collar */}
      <path d="M450 640 l-22 18 l22 120 l22 -120 z" fill={C.orange} />
      <path d="M420 624 l30 30 l30 -30" fill="none" stroke={C.white} strokeWidth={6} strokeLinecap="round" strokeLinejoin="round" />

      {/* Icons */}
      <IconTile x={640} y={560} size={78} bg={C.orangeTint} icon={Briefcase} color={C.orange} iconScale={0.55} />
      <IconTile x={160} y={560} size={78} bg={C.panel} icon={Building2} color={C.navy} iconScale={0.55} />

      {/* Title chip */}
      <Card x={250} y={930} w={400} h={92} r={24} fill={C.panel}>
        <IconBadge cx={304} cy={976} r={30} bg={C.navy} icon={Briefcase} iconScale={1.0} />
        <text x={350} y={966} fontFamily="system-ui, sans-serif" fontSize={24} fill={C.ink} fontWeight={800}>Strategic lead</text>
        <text x={350} y={998} fontFamily="system-ui, sans-serif" fontSize={18} fill={C.slate}>partnerships &amp; growth</text>
      </Card>
    </svg>
  );
}

/* Partner INVESTOR faq — confident woman professional, trend chip */
export function PortraitInvestor() {
  return (
    <svg viewBox="0 0 900 1100" width="100%" height="100%" preserveAspectRatio="xMidYMid meet" aria-hidden role="presentation">
      <rect x={0} y={0} width={PW} height={PH} fill={C.panelSoft} />
      <Blob cx={720} cy={240} r={300} color={C.blueSoft} opacity={0.6} />
      <Blob cx={180} cy={900} r={280} color={C.goldSoft} opacity={0.6} />

      {/* Growth chart card behind */}
      <Card x={140} y={140} w={620} h={340} r={28} fill={C.panel}>
        <text x={180} y={196} fontFamily="system-ui, sans-serif" fontSize={22} fill={C.ink} fontWeight={800}>Returns</text>
        <g transform="translate(180 210)"><TrendingUp width={26} height={26} color={C.green} strokeWidth={2.6} /></g>
        <text x={218} y={232} fontFamily="system-ui, sans-serif" fontSize={22} fill={C.green} fontWeight={800}>+32%</text>
        <LineChart x={180} y={252} w={540} h={196} points={[0.2, 0.35, 0.3, 0.55, 0.5, 0.74, 0.92]} color={C.blue} fill={C.blueTint} />
      </Card>

      {/* Person — blue blazer */}
      <g transform="translate(450 400)">
        <Person cx={0} topY={0} scale={1.8} skin={C.skin2} shirt={C.blue} />
      </g>

      {/* Gold accent badge */}
      <IconBadge cx={680} cy={620} r={48} bg={C.gold} icon={TrendingUp} color={C.navy} iconScale={1.0} />

      {/* Trend chip */}
      <Card x={130} y={580} w={250} h={84} r={22} fill={C.navy} stroke={C.navy}>
        <IconBadge cx={180} cy={622} r={28} bg={C.gold} icon={TrendingUp} color={C.navy} iconScale={1.0} />
        <text x={222} y={616} fontFamily="system-ui, sans-serif" fontSize={22} fill={C.white} fontWeight={800}>Investor</text>
        <text x={222} y={644} fontFamily="system-ui, sans-serif" fontSize={17} fill={C.blueSky}>relations</text>
      </Card>

      {/* Name chip */}
      <Card x={250} y={940} w={400} h={90} r={24} fill={C.panel}>
        <circle cx={302} cy={985} r={14} fill={C.orange} />
        <text x={332} y={974} fontFamily="system-ui, sans-serif" fontSize={24} fill={C.ink} fontWeight={800}>Growth partner</text>
        <text x={332} y={1004} fontFamily="system-ui, sans-serif" fontSize={18} fill={C.slate}>XAF-backed upside</text>
      </Card>
    </svg>
  );
}

/* Partner SERVICE faq — engineer/freelancer at a desk */
export function PortraitEngineer() {
  return (
    <svg viewBox="0 0 900 1100" width="100%" height="100%" preserveAspectRatio="xMidYMid meet" aria-hidden role="presentation">
      <rect x={0} y={0} width={PW} height={PH} fill={C.blueTint} />
      <Blob cx={210} cy={240} r={300} color={C.orangeSoft} opacity={0.45} />
      <Blob cx={720} cy={900} r={280} color={C.blueSoft} opacity={0.6} />

      {/* Code window behind */}
      <AppWindow x={140} y={140} w={620} h={320} title="api.ts" accent={C.blue}>
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <g key={i}>
            <rect x={172} y={200 + i * 38} width={16} height={16} rx={4} fill={i % 2 ? C.orange : C.blue} opacity={0.7} />
            <rect x={200} y={204 + i * 38} width={[300, 220, 360, 260, 320, 200][i]} height={10} rx={5} fill={i === 2 ? C.orangeSoft : C.panelMute} />
          </g>
        ))}
      </AppWindow>

      {/* Person with headphones hint */}
      <g transform="translate(450 430)">
        <Person
          cx={0}
          topY={0}
          scale={1.75}
          skin={C.skin3}
          shirt={C.blue}
          accessory={
            <g>
              {/* headphone band + cups */}
              <path d="M-92 14 a92 92 0 0 1 184 0" fill="none" stroke={C.ink} strokeWidth={12} strokeLinecap="round" />
              <rect x={-104} y={6} width={28} height={48} rx={12} fill={C.orange} />
              <rect x={76} y={6} width={28} height={48} rx={12} fill={C.orange} />
            </g>
          }
        />
      </g>

      {/* Laptop in front */}
      <rect x={330} y={870} width={240} height={130} rx={12} fill={C.panel} stroke={C.line} strokeWidth={3} />
      <rect x={352} y={888} width={196} height={94} rx={8} fill={C.navy} />
      {[0, 1, 2].map((i) => (
        <rect key={i} x={368} y={906 + i * 24} width={[150, 110, 130][i]} height={10} rx={5} fill={i === 0 ? C.orange : C.blueLight} opacity={0.8} />
      ))}
      <rect x={300} y={1000} width={300} height={16} rx={8} fill={C.steel} />

      {/* Code icon tile */}
      <IconTile x={630} y={560} size={80} bg={C.orange} icon={Code2} color={C.white} iconScale={0.55} />

      {/* Title chip */}
      <Card x={120} y={580} w={260} h={84} r={22} fill={C.navy} stroke={C.navy}>
        <IconBadge cx={172} cy={622} r={28} bg={C.blue} icon={Code2} iconScale={1.0} />
        <text x={214} y={616} fontFamily="system-ui, sans-serif" fontSize={22} fill={C.white} fontWeight={800}>Engineer</text>
        <text x={214} y={644} fontFamily="system-ui, sans-serif" fontSize={17} fill={C.blueSky}>service partner</text>
      </Card>
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/* CONTACT hero — friendly support agent with headset                 */
/* ------------------------------------------------------------------ */
export function SupportAgent() {
  const W = 1200;
  const H = 900;
  return (
    <svg viewBox="0 0 1200 900" width="100%" height="100%" preserveAspectRatio="xMidYMid meet" aria-hidden role="presentation">
      <rect x={0} y={0} width={W} height={H} fill={C.orangeTint} />
      <Blob cx={950} cy={210} r={300} color={C.blueSoft} opacity={0.7} />
      <Blob cx={230} cy={760} r={280} color={C.orangeSoft} opacity={0.55} />
      <Dots x={70} y={700} cols={9} rows={4} color={C.blue} opacity={0.15} />

      {/* Agent with headset */}
      <g transform="translate(310 320)">
        <Person
          cx={0}
          topY={0}
          scale={1.7}
          skin={C.skin2}
          shirt={C.orange}
          accessory={
            <g>
              {/* headset band + mic */}
              <path d="M-90 6 a90 90 0 0 1 180 0" fill="none" stroke={C.navy} strokeWidth={12} strokeLinecap="round" />
              <rect x={-102} y={-2} width={26} height={44} rx={11} fill={C.navy} />
              <rect x={76} y={-2} width={26} height={44} rx={11} fill={C.navy} />
              <path d="M76 40 q-10 40 -54 46" fill="none" stroke={C.navy} strokeWidth={8} strokeLinecap="round" />
              <circle cx={20} cy={90} r={8} fill={C.orange} />
            </g>
          }
        />
      </g>

      {/* Chat bubbles */}
      <g>
        <Card x={170} y={120} w={220} h={80} r={22} fill={C.blue} stroke={C.blue}>
          <g transform="translate(196 148)"><MessageCircle width={28} height={28} color={C.white} strokeWidth={2.2} /></g>
          <rect x={240} y={146} width={120} height={10} rx={5} fill={C.white} opacity={0.85} />
          <rect x={240} y={166} width={84} height={10} rx={5} fill={C.blueSky} />
        </Card>
        <path d="M210 196 l-6 28 l30 -16 z" fill={C.blue} />
      </g>

      {/* Inbox window with reply rows */}
      <AppWindow x={620} y={130} w={520} h={620} title="Inbox" accent={C.orange}>
        <Card x={652} y={186} w={456} h={92} r={18} fill={C.navy} stroke={C.navy}>
          <IconBadge cx={704} cy={232} r={30} bg={C.green} icon={MessageCircle} iconScale={1.0} />
          <text x={748} y={222} fontFamily="system-ui, sans-serif" fontSize={22} fill={C.white} fontWeight={800}>We reply within 1 day</text>
          <text x={748} y={252} fontFamily="system-ui, sans-serif" fontSize={18} fill={C.blueSky}>Mon–Fri · Bamenda time</text>
        </Card>
        <ListRows x={652} y={300} w={456} rows={5} rowH={64} gap={14} lead={C.orangeSoft} tag="new" />
      </AppWindow>

      {/* Reply chip */}
      <IconBadge cx={520} cy={210} r={34} bg={C.green} icon={BadgeCheck} iconScale={1.0} />

      {/* Headphones hint icon */}
      <IconBadge cx={170} cy={560} r={34} bg={C.navy} icon={Headphones} iconScale={1.0} />
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/* Partner STRATEGIC hero — two execs at a boardroom, deal handshake  */
/* ------------------------------------------------------------------ */
export function Boardroom() {
  const W = 1200;
  const H = 900;
  return (
    <svg viewBox="0 0 1200 900" width="100%" height="100%" preserveAspectRatio="xMidYMid meet" aria-hidden role="presentation">
      <rect x={0} y={0} width={W} height={H} fill={C.blueTint} />
      <Blob cx={250} cy={220} r={300} color={C.orangeSoft} opacity={0.5} />
      <Blob cx={970} cy={770} r={300} color={C.blueSoft} opacity={0.7} />

      {/* Presentation window with chart behind */}
      <AppWindow x={360} y={90} w={480} h={300} title="Deal terms" accent={C.orange}>
        <text x={392} y={170} fontFamily="system-ui, sans-serif" fontSize={20} fill={C.slate} fontWeight={600}>Projected growth</text>
        <BarChart x={392} y={196} w={416} h={160} values={[0.3, 0.45, 0.4, 0.6, 0.7, 0.85, 1]} color={C.orange} />
      </AppWindow>

      {/* Boardroom table */}
      <rect x={250} y={690} width={700} height={140} rx={26} fill={C.navy} />
      <rect x={250} y={690} width={700} height={24} rx={12} fill={C.navyDeep} />

      {/* Two execs facing each other */}
      <g transform="translate(420 470)">
        <Person cx={0} topY={0} scale={1.25} skin={C.skin1} shirt={C.navy} />
      </g>
      <g transform="translate(780 470)">
        <Person cx={0} topY={0} scale={1.25} skin={C.skin3} shirt={C.orange} />
      </g>

      {/* Handshake / deal card center */}
      <Card x={490} y={620} w={220} h={150} r={24}>
        <IconBadge cx={600} cy={672} r={36} bg={C.orange} icon={Handshake} iconScale={1.0} />
        <text x={600} y={730} textAnchor="middle" fontFamily="system-ui, sans-serif" fontSize={22} fill={C.ink} fontWeight={800}>Deal signed</text>
        <text x={600} y={756} textAnchor="middle" fontFamily="system-ui, sans-serif" fontSize={16} fill={C.slate}>strategic partner</text>
      </Card>

      {/* Building / partner badges */}
      <IconBadge cx={150} cy={250} r={36} bg={C.navy} icon={Building2} iconScale={1.0} />
      <IconBadge cx={1050} cy={250} r={36} bg={C.blue} icon={Briefcase} iconScale={1.0} />

      <Dots x={120} y={840} cols={14} rows={2} color={C.navy} opacity={0.16} />
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/* Partner STRATEGIC sidebar — two pros over a shared laptop          */
/* ------------------------------------------------------------------ */
export function Meeting() {
  const W = 1200;
  const H = 900;
  return (
    <svg viewBox="0 0 1200 900" width="100%" height="100%" preserveAspectRatio="xMidYMid meet" aria-hidden role="presentation">
      <rect x={0} y={0} width={W} height={H} fill={C.panelSoft} />
      <Blob cx={300} cy={240} r={300} color={C.orangeSoft} opacity={0.45} />
      <Blob cx={930} cy={760} r={300} color={C.blueSoft} opacity={0.6} />

      {/* Document card with list rows */}
      <Card x={760} y={150} w={360} h={560} r={28}>
        <text x={796} y={210} fontFamily="system-ui, sans-serif" fontSize={24} fill={C.ink} fontWeight={800}>Proposal</text>
        <g transform="translate(1066 188)"><Briefcase width={26} height={26} color={C.blue} strokeWidth={2.2} /></g>
        <ListRows x={796} y={236} w={288} rows={6} rowH={62} gap={14} lead={C.blueSoft} tag="ok" />
      </Card>

      {/* Two people collaborating */}
      <g transform="translate(330 350)">
        <Person cx={0} topY={0} scale={1.3} skin={C.skin2} shirt={C.blue} />
      </g>
      <g transform="translate(560 380)">
        <Person cx={0} topY={0} scale={1.2} skin={C.skin1} shirt={C.orange} />
      </g>

      {/* Shared laptop */}
      <rect x={300} y={650} width={340} height={140} rx={16} fill={C.navy} />
      <rect x={324} y={668} width={292} height={104} rx={10} fill={C.panel} />
      <rect x={344} y={688} width={252} height={12} rx={6} fill={C.orange} opacity={0.85} />
      <BarChart x={344} y={712} w={252} h={48} values={[0.4, 0.6, 0.5, 0.8, 0.7, 1]} color={C.blue} />
      <rect x={270} y={790} width={400} height={18} rx={9} fill={C.steel} />

      <Dots x={120} y={820} cols={9} rows={3} color={C.navy} opacity={0.14} />
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/* Partner SERVICE sidebar — a developer at a laptop                  */
/* ------------------------------------------------------------------ */
export function Developer() {
  const W = 1200;
  const H = 900;
  return (
    <svg viewBox="0 0 1200 900" width="100%" height="100%" preserveAspectRatio="xMidYMid meet" aria-hidden role="presentation">
      <rect x={0} y={0} width={W} height={H} fill={C.blueTint} />
      <Blob cx={950} cy={230} r={300} color={C.orangeSoft} opacity={0.5} />
      <Blob cx={230} cy={770} r={280} color={C.blueSoft} opacity={0.6} />
      <Dots x={70} y={700} cols={9} rows={4} color={C.navy} opacity={0.14} />

      {/* Code editor window */}
      <AppWindow x={560} y={120} w={580} h={520} title="terminal" accent={C.orange}>
        {/* code lines */}
        {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
          <g key={i}>
            <rect x={592} y={186 + i * 50} width={20} height={14} rx={4} fill={i % 2 ? C.orange : C.blue} opacity={0.7} />
            <rect x={624} y={188 + i * 50} width={[260, 360, 200, 420, 300, 380, 240, 320][i]} height={12} rx={6} fill={i === 3 ? C.orangeSoft : i === 5 ? C.blueSoft : C.panelMute} />
            <rect x={624 + [260, 360, 200, 420, 300, 380, 240, 320][i] + 20} y={188 + i * 50} width={i % 3 === 0 ? 60 : 40} height={12} rx={6} fill={C.lineSoft} />
          </g>
        ))}
        {/* terminal glyph */}
        <g transform="translate(1066 168)"><Terminal width={28} height={28} color={C.navy} strokeWidth={2.2} /></g>
      </AppWindow>

      {/* Developer */}
      <g transform="translate(290 380)">
        <Person cx={0} topY={0} scale={1.4} skin={C.skin1} shirt={C.blue} />
      </g>

      {/* Laptop, hands on keyboard */}
      <rect x={150} y={690} width={340} height={150} rx={16} fill={C.navy} />
      <rect x={176} y={710} width={288} height={112} rx={10} fill={C.panel} />
      {[0, 1, 2].map((i) => (
        <rect key={i} x={198} y={732 + i * 28} width={[200, 150, 180][i]} height={12} rx={6} fill={i === 0 ? C.orange : C.blueLight} opacity={0.85} />
      ))}
      <rect x={120} y={840} width={400} height={18} rx={9} fill={C.steel} />

      {/* API / braces hint */}
      <Card x={120} y={560} w={250} h={80} r={20} fill={C.navy} stroke={C.navy}>
        <text x={150} y={612} fontFamily="system-ui, sans-serif" fontSize={34} fill={C.orange} fontWeight={800}>{"{ }"}</text>
        <text x={208} y={596} fontFamily="system-ui, sans-serif" fontSize={20} fill={C.white} fontWeight={800}>REST API</text>
        <text x={208} y={624} fontFamily="system-ui, sans-serif" fontSize={16} fill={C.blueSky}>integrate fast</text>
      </Card>

      {/* Code icon tile */}
      <IconTile x={1066} y={660} size={70} bg={C.orange} icon={Code2} color={C.white} iconScale={0.55} />
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/* CONTACT office — modern HQ tower + Bamenda map pin                  */
/* ------------------------------------------------------------------ */
export function OfficeHQ() {
  const W = 1200;
  const H = 900;
  return (
    <svg viewBox="0 0 1200 900" width="100%" height="100%" preserveAspectRatio="xMidYMid meet" aria-hidden role="presentation">
      <rect x={0} y={0} width={W} height={H} fill={C.blueTint} />
      <Blob cx={250} cy={220} r={300} color={C.orangeSoft} opacity={0.45} />
      <Blob cx={960} cy={770} r={300} color={C.blueSoft} opacity={0.7} />
      <Dots x={70} y={720} cols={11} rows={3} color={C.navy} opacity={0.14} />

      {/* HQ tower */}
      <rect x={160} y={180} width={360} height={600} rx={26} fill={C.navy} />
      <rect x={160} y={180} width={360} height={600} rx={26} fill="none" stroke={C.navyDeep} strokeWidth={6} />
      {/* window grid */}
      {Array.from({ length: 40 }).map((_, i) => {
        const col = i % 4;
        const row = Math.floor(i / 4);
        const lit = (col + row) % 3 === 0;
        return (
          <rect
            key={i}
            x={196 + col * 78}
            y={236 + row * 52}
            width={58}
            height={34}
            rx={6}
            fill={lit ? C.orange : C.blue}
            opacity={lit ? 0.85 : 0.4}
          />
        );
      })}
      {/* entrance */}
      <rect x={300} y={720} width={80} height={60} rx={8} fill={C.orange} />

      {/* Roof badge */}
      <IconBadge cx={340} cy={150} r={36} bg={C.orange} icon={Building2} iconScale={1.0} />

      {/* HQ label */}
      <Card x={160} y={810} w={360} h={64} r={18} fill={C.panel}>
        <g transform="translate(186 826)"><Building2 width={28} height={28} color={C.navy} strokeWidth={2.2} /></g>
        <text x={228} y={850} fontFamily="system-ui, sans-serif" fontSize={24} fill={C.ink} fontWeight={800}>QUATA DIGITAL HQ</text>
      </Card>

      {/* Big map pin */}
      <g transform="translate(820 300)">
        <Pin cx={0} cy={120} size={150} color={C.orange} />
      </g>
      <Card x={700} y={420} w={420} h={70} r={20} fill={C.panel}>
        <g transform="translate(726 438)"><MapPin width={28} height={28} color={C.orange} strokeWidth={2.4} /></g>
        <text x={768} y={462} fontFamily="system-ui, sans-serif" fontSize={26} fill={C.ink} fontWeight={800}>Bamenda, Cameroon</text>
      </Card>

      {/* Small map card */}
      <Card x={700} y={520} w={420} h={260} r={24} fill={C.panelSoft}>
        {/* roads */}
        <path d="M720 620 h380" stroke={C.line} strokeWidth={8} strokeLinecap="round" />
        <path d="M720 700 h380" stroke={C.line} strokeWidth={8} strokeLinecap="round" />
        <path d="M830 540 v220" stroke={C.line} strokeWidth={8} strokeLinecap="round" />
        <path d="M990 540 v220" stroke={C.line} strokeWidth={8} strokeLinecap="round" />
        {/* blocks */}
        <rect x={736} y={552} width={78} height={56} rx={8} fill={C.blueSoft} />
        <rect x={1004} y={636} width={84} height={56} rx={8} fill={C.orangeSoft} />
        <rect x={846} y={716} width={130} height={48} rx={8} fill={C.blueSoft} opacity={0.7} />
        {/* pin on map */}
        <Pin cx={910} cy={650} size={48} color={C.orange} />
      </Card>
    </svg>
  );
}
