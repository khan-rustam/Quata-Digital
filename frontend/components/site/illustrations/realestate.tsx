/**
 * Real-estate illustrations (88BRICKZ — property listings + management).
 * Same flat product-mockup style as payments.tsx: orange #FF6B00 + Quata blue,
 * neutral surfaces, embedded lucide glyphs, African skin tones for people.
 *
 * Landscape art uses the 4:3 viewBox (1200 x 900).
 */
import * as React from "react";
import {
  Home,
  MapPin,
  BadgeCheck,
  Wallet,
  Banknote,
  Building2,
  KeyRound,
  ArrowUpRight,
} from "lucide-react";
import { C } from "./palette";
import { Card, Pill, IconBadge, IconTile, BarChart, Dots, Blob } from "./kit";

const VB = "0 0 1200 900";

/** 88BRICKZ hero — property card, listings, rent collection + verified landlord. */
export function RealEstate() {
  return (
    <svg viewBox={VB} width="100%" height="100%" preserveAspectRatio="xMidYMid meet" aria-hidden role="presentation">
      <rect x={0} y={0} width={1200} height={900} fill={C.orangeTint} />
      <Blob cx={250} cy={210} r={300} color={C.orangeSoft} opacity={0.5} />
      <Blob cx={1010} cy={760} r={300} color={C.blueSoft} opacity={0.7} />
      <Dots x={70} y={650} cols={9} rows={5} color={C.blue} opacity={0.14} />

      {/* ── Featured property card (modern building) ─────────────────── */}
      <Card x={120} y={120} w={470} h={470} r={26}>
        {/* sky / scene background */}
        <rect x={148} y={150} width={414} height={250} rx={18} fill={C.blueTint} />
        <Blob cx={500} cy={210} r={70} color={C.gold} opacity={0.45} />

        {/* roof */}
        <path d="M280 250 L355 196 L430 250 Z" fill={C.orange} />
        <path d="M280 250 L355 196 L430 250 Z" fill="none" stroke={C.orangeDark} strokeWidth={3} strokeLinejoin="round" />
        {/* building body */}
        <rect x={296} y={250} width={118} height={150} rx={8} fill={C.navy} />
        <rect x={296} y={250} width={118} height={150} rx={8} fill="none" stroke={C.navyDeep} strokeWidth={3} />
        {/* windows */}
        {[0, 1].map((cI) =>
          [0, 1].map((rI) => (
            <rect
              key={`${cI}-${rI}`}
              x={316 + cI * 46}
              y={272 + rI * 44}
              width={32}
              height={32}
              rx={5}
              fill={C.blueLight}
            />
          )),
        )}
        {/* door */}
        <rect x={342} y={356} width={26} height={44} rx={5} fill={C.orangeSoft} />
        <circle cx={362} cy={380} r={2.6} fill={C.orangeDark} />

        {/* "For rent" price chip */}
        <g transform="translate(0 0)">
          <rect x={170} y={172} width={186} height={48} rx={24} fill={C.orange} />
          <g transform="translate(186 184)"><KeyRound width={24} height={24} color={C.white} strokeWidth={2.4} /></g>
          <text x={220} y={202} fontFamily="system-ui, sans-serif" fontSize={22} fill={C.white} fontWeight={800}>XAF 120k/mo</text>
        </g>
        {/* "For rent" tag */}
        <rect x={432} y={356} width={104} height={30} rx={15} fill={C.greenSoft} />
        <text x={448} y={376} fontFamily="system-ui, sans-serif" fontSize={16} fill={C.green} fontWeight={800}>For rent</text>

        {/* card meta */}
        <text x={150} y={444} fontFamily="system-ui, sans-serif" fontSize={26} fill={C.ink} fontWeight={800}>2-bed apartment</text>
        <g transform="translate(150 462)"><MapPin width={20} height={20} color={C.orange} strokeWidth={2.4} /></g>
        <text x={178} y={478} fontFamily="system-ui, sans-serif" fontSize={18} fill={C.slate} fontWeight={600}>Bamenda · Cameroon</text>

        {/* spec pills */}
        <Pill x={150} y={502} w={112} h={32} fill={C.orangeTint} />
        <g transform="translate(166 510)"><Home width={18} height={18} color={C.orange} strokeWidth={2.4} /></g>
        <text x={192} y={523} fontFamily="system-ui, sans-serif" fontSize={15} fill={C.orangeDark} fontWeight={700}>2 rooms</text>
        <Pill x={274} y={502} w={120} h={32} fill={C.blueTint} />
        <g transform="translate(290 510)"><Building2 width={18} height={18} color={C.blue} strokeWidth={2.4} /></g>
        <text x={316} y={523} fontFamily="system-ui, sans-serif" fontSize={15} fill={C.blue} fontWeight={700}>Floor 3</text>

        {/* Verified landlord badge row */}
        <rect x={150} y={546} width={388} height={2} fill={C.line} />
        <IconBadge cx={172} cy={570} r={20} bg={C.green} icon={BadgeCheck} iconScale={1.05} />
        <text x={202} y={576} fontFamily="system-ui, sans-serif" fontSize={17} fill={C.ink} fontWeight={700}>Verified landlord</text>
      </Card>

      {/* ── Listings panel ──────────────────────────────────────────── */}
      <Card x={616} y={120} w={464} h={300} r={26}>
        <g transform="translate(644 152)"><Home width={26} height={26} color={C.orange} strokeWidth={2.4} /></g>
        <text x={682} y={174} fontFamily="system-ui, sans-serif" fontSize={24} fill={C.ink} fontWeight={800}>Property listings</text>
        <rect x={974} y={152} width={82} height={28} rx={14} fill={C.blueSoft} />
        <text x={988} y={172} fontFamily="system-ui, sans-serif" fontSize={15} fill={C.blue} fontWeight={700}>48 live</text>

        {[0, 1, 2].map((i) => {
          const ry = 202 + i * 68;
          return (
            <g key={i}>
              <rect x={644} y={ry} width={412} height={56} rx={14} fill={C.panel} stroke={C.lineSoft} strokeWidth={2} />
              <IconTile
                x={656}
                y={ry + 10}
                size={36}
                r={10}
                bg={i === 1 ? C.blueTint : C.orangeTint}
                icon={i === 1 ? MapPin : Home}
                color={i === 1 ? C.blue : C.orange}
                iconScale={0.56}
              />
              <text x={706} y={ry + 24} fontFamily="system-ui, sans-serif" fontSize={17} fill={C.ink} fontWeight={700}>
                {i === 0 ? "Studio · Up Station" : i === 1 ? "3-bed villa · Nkwen" : "Shop unit · City centre"}
              </text>
              <text x={706} y={ry + 44} fontFamily="system-ui, sans-serif" fontSize={14} fill={C.slate} fontWeight={600}>
                {i === 0 ? "XAF 65k/mo" : i === 1 ? "XAF 240k/mo" : "XAF 180k/mo"}
              </text>
              {/* Verified green tag */}
              <rect x={952} y={ry + 17} width={92} height={24} rx={12} fill={C.greenSoft} />
              <g transform={`translate(963 ${ry + 21})`}><BadgeCheck width={16} height={16} color={C.green} strokeWidth={2.4} /></g>
              <text x={985} y={ry + 34} fontFamily="system-ui, sans-serif" fontSize={13} fill={C.green} fontWeight={800}>Verified</text>
            </g>
          );
        })}
      </Card>

      {/* ── Rent collection card ────────────────────────────────────── */}
      <Card x={616} y={444} w={278} h={336} r={26}>
        <IconBadge cx={650} cy={488} r={26} bg={C.orange} icon={Wallet} iconScale={0.95} />
        <text x={686} y={482} fontFamily="system-ui, sans-serif" fontSize={19} fill={C.ink} fontWeight={800}>Rent collected</text>
        <text x={686} y={506} fontFamily="system-ui, sans-serif" fontSize={14} fill={C.slate} fontWeight={600}>This month</text>

        <text x={644} y={560} fontFamily="system-ui, sans-serif" fontSize={34} fill={C.orange} fontWeight={800}>XAF 4.2M</text>
        <g transform="translate(644 574)"><ArrowUpRight width={20} height={20} color={C.green} strokeWidth={2.8} /></g>
        <text x={670} y={590} fontFamily="system-ui, sans-serif" fontSize={16} fill={C.green} fontWeight={700}>+12% vs last</text>

        <BarChart x={644} y={612} w={222} h={120} values={[0.42, 0.55, 0.48, 0.7, 0.62, 0.85, 1]} color={C.orange} />
        <text x={644} y={756} fontFamily="system-ui, sans-serif" fontSize={13} fill={C.steel} fontWeight={600}>Jan – Jul</text>
      </Card>

      {/* ── Verified landlord card ──────────────────────────────────── */}
      <Card x={912} y={444} w={168} h={336} r={26} fill={C.navy} stroke={C.navy}>
        <IconBadge cx={996} cy={520} r={42} bg={C.green} icon={BadgeCheck} iconScale={1.05} />
        <text x={996} y={596} textAnchor="middle" fontFamily="system-ui, sans-serif" fontSize={20} fill={C.white} fontWeight={800}>Verified</text>
        <text x={996} y={624} textAnchor="middle" fontFamily="system-ui, sans-serif" fontSize={20} fill={C.white} fontWeight={800}>landlord</text>
        <rect x={940} y={648} width={112} height={2} fill={C.blue} opacity={0.5} />
        <IconBadge cx={964} cy={696} r={22} bg={C.orange} icon={Banknote} iconScale={0.92} />
        <text x={996} y={702} fontFamily="system-ui, sans-serif" fontSize={15} fill={C.blueSky} fontWeight={700}>Secure</text>
        <text x={996} y={722} fontFamily="system-ui, sans-serif" fontSize={15} fill={C.blueSky} fontWeight={700}>payouts</text>
      </Card>
    </svg>
  );
}
