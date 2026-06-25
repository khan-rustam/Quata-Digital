/**
 * Payments illustrations (QUATAPAY + merchant payments).
 * Style reference for the whole illustration set: flat product-mockup look,
 * orange #FF6B00 + Quata blue, neutral surfaces, embedded lucide glyphs.
 *
 * All landscape arts use a 4:3 viewBox (1200 x 900).
 */
import * as React from "react";
import {
  QrCode,
  Wallet,
  BadgeCheck,
  Banknote,
  ArrowUpRight,
  Store,
  CreditCard,
  Nfc,
  Smartphone,
} from "lucide-react";
import { C } from "./palette";
import { Card, Pill, IconBadge, IconTile, Phone, BarChart, Dots, Blob, Person } from "./kit";

const VB = "0 0 1200 900";

/** QUATAPAY hero — phone wallet + "payment received" + QR + volume chart. */
export function PaymentsApp() {
  return (
    <svg viewBox={VB} width="100%" height="100%" preserveAspectRatio="xMidYMid meet" aria-hidden role="presentation">
      <rect x={0} y={0} width={1200} height={900} fill={C.blueTint} />
      <Blob cx={250} cy={210} r={300} color={C.orangeSoft} opacity={0.5} />
      <Blob cx={1010} cy={760} r={300} color={C.blueSoft} opacity={0.7} />
      <Dots x={70} y={640} cols={9} rows={5} color={C.blue} opacity={0.16} />

      {/* Phone — MoMo + card balance */}
      <Phone x={150} y={120} w={420} h={660}>
        <rect x={170} y={150} width={380} height={120} rx={20} fill={C.navy} />
        <text x={196} y={196} fontFamily="system-ui, sans-serif" fontSize={20} fill={C.blueSky} fontWeight={600}>QUATAPAY balance</text>
        <text x={196} y={238} fontFamily="system-ui, sans-serif" fontSize={34} fill={C.white} fontWeight={800}>XAF 248,500</text>
        <IconTile x={486} y={166} size={44} bg={C.orange} icon={Wallet} color={C.white} iconScale={0.58} />

        {/* channel chips */}
        <IconBadge cx={210} cy={326} r={26} bg={C.orangeTint} icon={Smartphone} color={C.orange} iconScale={0.9} />
        <IconBadge cx={290} cy={326} r={26} bg={C.blueSoft} icon={CreditCard} color={C.blue} iconScale={0.9} />
        <IconBadge cx={370} cy={326} r={26} bg={C.goldSoft} icon={QrCode} color={C.orangeDark} iconScale={0.9} />
        <Pill x={420} y={312} w={110} h={28} fill={C.panelMute} />

        {/* transaction rows */}
        {[0, 1, 2].map((i) => (
          <g key={i}>
            <rect x={170} y={380 + i * 78} width={380} height={62} rx={14} fill={C.panel} stroke={C.lineSoft} strokeWidth={2} />
            <circle cx={204} cy={411 + i * 78} r={18} fill={i === 0 ? C.greenSoft : C.blueSoft} />
            <rect x={236} y={396 + i * 78} width={150} height={9} rx={4.5} fill={C.panelMute} />
            <rect x={236} y={414 + i * 78} width={90} height={8} rx={4} fill={C.lineSoft} />
            <rect x={470} y={402 + i * 78} width={62} height={18} rx={9} fill={i === 0 ? C.green : C.navy} />
          </g>
        ))}
      </Phone>

      {/* Floating "payment received" card */}
      <Card x={612} y={150} w={470} h={150} r={22}>
        <IconBadge cx={672} cy={225} r={36} bg={C.green} icon={BadgeCheck} iconScale={1.0} />
        <text x={726} y={210} fontFamily="system-ui, sans-serif" fontSize={24} fill={C.ink} fontWeight={700}>Payment received</text>
        <text x={726} y={246} fontFamily="system-ui, sans-serif" fontSize={20} fill={C.slate}>MTN MoMo · settled instantly</text>
        <text x={726} y={282} fontFamily="system-ui, sans-serif" fontSize={26} fill={C.orange} fontWeight={800}>+ XAF 15,000</text>
      </Card>

      {/* QR pay card */}
      <Card x={612} y={328} w={222} h={300} r={22}>
        <text x={636} y={372} fontFamily="system-ui, sans-serif" fontSize={18} fill={C.slate} fontWeight={600}>Scan to pay</text>
        <rect x={636} y={392} width={174} height={174} rx={16} fill={C.panelSoft} stroke={C.line} strokeWidth={2} />
        <g transform="translate(681 437)"><QrCode width={84} height={84} color={C.navy} strokeWidth={2} /></g>
        <Pill x={636} y={584} w={174} h={26} fill={C.orangeTint} />
      </Card>

      {/* Settlement volume card */}
      <Card x={852} y={328} w={230} h={300} r={22}>
        <text x={876} y={372} fontFamily="system-ui, sans-serif" fontSize={18} fill={C.slate} fontWeight={600}>Weekly volume</text>
        <g transform="translate(876 392)"><ArrowUpRight width={22} height={22} color={C.green} strokeWidth={2.6} /></g>
        <text x={876} y={430} fontFamily="system-ui, sans-serif" fontSize={28} fill={C.ink} fontWeight={800}>+18%</text>
        <BarChart x={876} y={452} w={182} h={150} values={[0.35, 0.5, 0.42, 0.66, 0.58, 0.8, 1]} color={C.orange} />
      </Card>

      {/* Merchant strip */}
      <Card x={612} y={656} w={470} h={120} r={22} fill={C.navy} stroke={C.navy}>
        <IconBadge cx={672} cy={716} r={34} bg={C.orange} icon={Store} iconScale={1.0} />
        <text x={724} y={702} fontFamily="system-ui, sans-serif" fontSize={22} fill={C.white} fontWeight={700}>One merchant account</text>
        <text x={724} y={736} fontFamily="system-ui, sans-serif" fontSize={18} fill={C.blueSky}>MoMo · cards · links · QR</text>
        <IconBadge cx={1040} cy={716} r={26} bg={C.blue} icon={Banknote} iconScale={0.9} />
      </Card>
    </svg>
  );
}

/** Partner / business merchant accepting a QR payment at the counter. */
export function MerchantPayment() {
  return (
    <svg viewBox={VB} width="100%" height="100%" preserveAspectRatio="xMidYMid meet" aria-hidden role="presentation">
      <rect x={0} y={0} width={1200} height={900} fill={C.orangeTint} />
      <Blob cx={950} cy={220} r={300} color={C.blueSoft} opacity={0.7} />
      <Blob cx={220} cy={760} r={260} color={C.orangeSoft} opacity={0.6} />

      {/* Shop awning */}
      <rect x={120} y={150} width={660} height={70} rx={14} fill={C.navy} />
      {Array.from({ length: 11 }).map((_, i) => (
        <rect key={i} x={132 + i * 60} y={150} width={30} height={70} fill={i % 2 ? C.orange : C.white} opacity={i % 2 ? 0.9 : 0.85} />
      ))}
      <rect x={120} y={150} width={660} height={70} rx={14} fill="none" stroke={C.navy} strokeWidth={3} />
      <text x={150} y={290} fontFamily="system-ui, sans-serif" fontSize={30} fill={C.ink} fontWeight={800}>QUATA-accepted shop</text>
      <Pill x={150} y={312} w={300} h={20} fill={C.orangeSoft} />

      {/* Counter */}
      <rect x={120} y={620} width={960} height={150} rx={20} fill={C.navy} />
      <rect x={120} y={620} width={960} height={26} rx={13} fill={C.navyDeep} />

      {/* Merchant behind counter */}
      <g transform="translate(300 350)">
        <Person cx={0} topY={0} scale={1.25} skin={C.skin2} shirt={C.orange} />
      </g>

      {/* Customer phone scanning QR */}
      <Card x={690} y={330} w={300} h={300} r={26}>
        <text x={720} y={378} fontFamily="system-ui, sans-serif" fontSize={20} fill={C.slate} fontWeight={600}>Tap · scan · paid</text>
        <rect x={720} y={398} width={150} height={150} rx={16} fill={C.panelSoft} stroke={C.line} strokeWidth={2} />
        <g transform="translate(757 435)"><QrCode width={76} height={76} color={C.navy} strokeWidth={2} /></g>
        <IconBadge cx={905} cy={418} r={30} bg={C.green} icon={BadgeCheck} iconScale={1.0} />
        <g transform="translate(884 470)"><Nfc width={44} height={44} color={C.orange} strokeWidth={2.4} /></g>
      </Card>

      <Dots x={120} y={800} cols={14} rows={2} color={C.navy} opacity={0.18} />
    </svg>
  );
}

/** Partner / business POS terminal + tap card + receipt. */
export function PosTerminal() {
  return (
    <svg viewBox={VB} width="100%" height="100%" preserveAspectRatio="xMidYMid meet" aria-hidden role="presentation">
      <rect x={0} y={0} width={1200} height={900} fill={C.panelSoft} />
      <Blob cx={300} cy={250} r={280} color={C.orangeSoft} opacity={0.5} />
      <Blob cx={950} cy={720} r={280} color={C.blueSoft} opacity={0.6} />

      {/* POS terminal body */}
      <rect x={360} y={150} width={420} height={560} rx={40} fill={C.navy} />
      <rect x={360} y={150} width={420} height={560} rx={40} fill="none" stroke={C.navyDeep} strokeWidth={6} />
      {/* screen */}
      <rect x={404} y={196} width={332} height={250} rx={18} fill={C.panel} />
      <text x={436} y={250} fontFamily="system-ui, sans-serif" fontSize={22} fill={C.slate} fontWeight={600}>Amount due</text>
      <text x={436} y={302} fontFamily="system-ui, sans-serif" fontSize={44} fill={C.ink} fontWeight={800}>XAF 9,500</text>
      <IconBadge cx={460} cy={372} r={26} bg={C.green} icon={BadgeCheck} iconScale={1.0} />
      <text x={500} y={382} fontFamily="system-ui, sans-serif" fontSize={22} fill={C.green} fontWeight={700}>Approved</text>
      {/* keypad */}
      {Array.from({ length: 12 }).map((_, i) => (
        <rect key={i} x={420 + (i % 3) * 108} y={476 + Math.floor(i / 3) * 56} width={84} height={42} rx={12} fill={C.navyDeep} />
      ))}

      {/* Tapping card */}
      <g transform="rotate(-18 880 360)">
        <rect x={770} y={300} width={300} height={186} rx={22} fill={C.orange} />
        <rect x={770} y={300} width={300} height={186} rx={22} fill="none" stroke={C.orangeDark} strokeWidth={3} />
        <rect x={800} y={336} width={48} height={38} rx={8} fill={C.goldSoft} />
        <g transform="translate(1006 320)"><Nfc width={36} height={36} color={C.white} strokeWidth={2.6} /></g>
        <Pill x={800} y={420} w={170} h={16} fill={C.white} />
        <Pill x={800} y={446} w={110} h={12} fill={C.orangeSoft} />
      </g>

      {/* Receipt */}
      <Card x={120} y={470} w={240} h={300} r={18}>
        <g transform="translate(150 502)"><CreditCard width={28} height={28} color={C.blue} strokeWidth={2.2} /></g>
        <text x={190} y={524} fontFamily="system-ui, sans-serif" fontSize={18} fill={C.ink} fontWeight={700}>Receipt</text>
        {[0, 1, 2, 3].map((i) => (
          <g key={i}>
            <rect x={150} y={556 + i * 34} width={120} height={9} rx={4.5} fill={C.panelMute} />
            <rect x={290} y={556 + i * 34} width={42} height={9} rx={4.5} fill={C.lineSoft} />
          </g>
        ))}
        <rect x={150} y={712} width={182} height={2} fill={C.line} />
        <text x={150} y={744} fontFamily="system-ui, sans-serif" fontSize={18} fill={C.orange} fontWeight={800}>Paid</text>
      </Card>
    </svg>
  );
}
