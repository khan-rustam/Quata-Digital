/**
 * Health illustrations (QMEDIQ — telemedicine + digital health).
 * Same flat product-mockup style as payments.tsx: orange #FF6B00 + Quata blue,
 * neutral surfaces, embedded lucide glyphs, African skin tones.
 *
 * All landscape arts use a 4:3 viewBox (1200 x 900).
 */
import * as React from "react";
import {
  Stethoscope,
  Video,
  Phone as PhoneIcon,
  Mic,
  Calendar,
  FileText,
  HeartPulse,
  User,
  ShieldCheck,
} from "lucide-react";
import { C } from "./palette";
import { Card, IconBadge, IconTile, Phone, ListRows, Dots, Blob, Person } from "./kit";

const VB = "0 0 1200 900";

/** QMEDIQ hero — virtual doctor consultation on a phone + appointment +
 *  digital medical records + patient avatar. Blue-led, orange accents. */
export function Telemedicine() {
  return (
    <svg viewBox={VB} width="100%" height="100%" preserveAspectRatio="xMidYMid meet" aria-hidden role="presentation">
      <rect x={0} y={0} width={1200} height={900} fill={C.blueTint} />
      <Blob cx={260} cy={210} r={300} color={C.blueSoft} opacity={0.7} />
      <Blob cx={1010} cy={760} r={300} color={C.orangeSoft} opacity={0.5} />
      <Dots x={70} y={650} cols={9} rows={5} color={C.blue} opacity={0.15} />

      {/* Phone — live video consultation with the doctor */}
      <Phone x={150} y={110} w={420} h={680}>
        {/* video stage */}
        <rect x={170} y={150} width={380} height={356} rx={22} fill={C.navy} />

        {/* doctor on the call (African, white/blue coat) */}
        <g transform="translate(0 6)">
          <Person cx={360} topY={196} scale={1.18} skin={C.skin2} shirt={C.blue} />
        </g>
        {/* white coat lapels over the shirt */}
        <path d="M310 470 L360 430 L360 506 L296 506 Z" fill={C.white} opacity={0.95} />
        <path d="M410 470 L360 430 L360 506 L424 506 Z" fill={C.white} opacity={0.95} />
        {/* stethoscope badge on the doctor */}
        <IconBadge cx={360} cy={452} r={20} bg={C.orange} icon={Stethoscope} color={C.white} iconScale={1.0} />

        {/* "live" + name tag */}
        <rect x={190} y={170} width={92} height={28} rx={14} fill={C.red} opacity={0.92} />
        <circle cx={208} cy={184} r={5} fill={C.white} />
        <text x={222} y={189} fontFamily="system-ui, sans-serif" fontSize={15} fill={C.white} fontWeight={700}>LIVE</text>
        <rect x={190} y={462} width={210} height={32} rx={10} fill={C.navyDeep} opacity={0.85} />
        <text x={204} y={484} fontFamily="system-ui, sans-serif" fontSize={16} fill={C.white} fontWeight={700}>Dr. Achidi · GP</text>

        {/* self-view (patient) thumbnail */}
        <rect x={444} y={372} width={94} height={120} rx={12} fill={C.navyDeep} stroke={C.blueMid} strokeWidth={2} />
        <circle cx={491} cy={418} r={22} fill={C.skin3} />
        <path d="M469 418 a22 22 0 0 1 44 0 q-22 -14 -44 0 Z" fill={C.hair} />
        <path d="M467 492 q24 -30 48 0 Z" fill={C.orange} />

        {/* call controls */}
        <IconBadge cx={250} cy={552} r={28} bg={C.blue} icon={Video} color={C.white} iconScale={0.92} />
        <IconBadge cx={330} cy={552} r={28} bg={C.panelMute} icon={Mic} color={C.navy} iconScale={0.92} />
        <IconBadge cx={460} cy={552} r={28} bg={C.red} icon={PhoneIcon} color={C.white} iconScale={0.92} />

        {/* consultation summary chips */}
        <rect x={170} y={602} width={380} height={70} rx={16} fill={C.panel} stroke={C.lineSoft} strokeWidth={2} />
        <IconTile x={186} y={618} size={38} bg={C.blueSoft} icon={Stethoscope} color={C.blue} iconScale={0.56} />
        <text x={238} y={632} fontFamily="system-ui, sans-serif" fontSize={16} fill={C.ink} fontWeight={700}>Virtual consult</text>
        <text x={238} y={656} fontFamily="system-ui, sans-serif" fontSize={14} fill={C.slate}>Bamenda · 12 min</text>
        <rect x={448} y={624} width={88} height={26} rx={13} fill={C.greenSoft} />
        <text x={462} y={642} fontFamily="system-ui, sans-serif" fontSize={13} fill={C.green} fontWeight={700}>Connected</text>

        {/* consult fee */}
        <rect x={170} y={684} width={380} height={64} rx={16} fill={C.orangeTint} />
        <IconBadge cx={206} cy={716} r={22} bg={C.orange} icon={HeartPulse} color={C.white} iconScale={0.95} />
        <text x={240} y={710} fontFamily="system-ui, sans-serif" fontSize={15} fill={C.slate} fontWeight={600}>Consult fee</text>
        <text x={240} y={734} fontFamily="system-ui, sans-serif" fontSize={18} fill={C.orangeDark} fontWeight={800}>XAF 3,500</text>
        <text x={470} y={724} fontFamily="system-ui, sans-serif" fontSize={16} fill={C.orange} fontWeight={800}>Pay</text>
      </Phone>

      {/* Appointment card */}
      <Card x={618} y={110} w={470} h={150} r={22}>
        <IconBadge cx={678} cy={185} r={36} bg={C.blue} icon={Calendar} iconScale={1.0} />
        <text x={732} y={168} fontFamily="system-ui, sans-serif" fontSize={24} fill={C.ink} fontWeight={700}>Next appointment</text>
        <text x={732} y={204} fontFamily="system-ui, sans-serif" fontSize={20} fill={C.slate}>Today · 14:30 · Dr. Achidi</text>
        <rect x={732} y={222} width={150} height={26} rx={13} fill={C.greenSoft} />
        <text x={748} y={240} fontFamily="system-ui, sans-serif" fontSize={14} fill={C.green} fontWeight={700}>Confirmed</text>
      </Card>

      {/* Digital medical records card */}
      <Card x={618} y={288} w={470} h={336} r={22}>
        <IconBadge cx={678} cy={344} r={28} bg={C.orange} icon={FileText} iconScale={0.95} />
        <text x={720} y={338} fontFamily="system-ui, sans-serif" fontSize={22} fill={C.ink} fontWeight={700}>Medical records</text>
        <text x={720} y={364} fontFamily="system-ui, sans-serif" fontSize={16} fill={C.slate}>Secure · synced</text>
        <g transform="translate(1028 326)"><HeartPulse width={34} height={34} color={C.red} strokeWidth={2.4} /></g>
        <ListRows x={650} y={392} w={406} rows={3} rowH={56} gap={14} lead={C.blueSoft} tag="ok" />
        <rect x={650} y={576} width={406} height={2} fill={C.line} />
        <g transform="translate(652 594)"><ShieldCheck width={22} height={22} color={C.green} strokeWidth={2.4} /></g>
        <text x={684} y={611} fontFamily="system-ui, sans-serif" fontSize={15} fill={C.slate} fontWeight={600}>End-to-end encrypted history</text>
      </Card>

      {/* Patient strip */}
      <Card x={618} y={652} w={470} h={136} r={22} fill={C.navy} stroke={C.navy}>
        <circle cx={684} cy={720} r={38} fill={C.skin1} />
        <path d="M646 720 a38 38 0 0 1 76 0 q-38 -24 -76 0 Z" fill={C.hair} />
        <path d="M650 758 q34 -40 68 0 Z" fill={C.orange} />
        <text x={742} y={702} fontFamily="system-ui, sans-serif" fontSize={22} fill={C.white} fontWeight={700}>Care from anywhere</text>
        <text x={742} y={736} fontFamily="system-ui, sans-serif" fontSize={17} fill={C.blueSky}>Doctors · records · follow-ups</text>
        <IconBadge cx={1040} cy={720} r={26} bg={C.orange} icon={User} iconScale={0.9} />
      </Card>
    </svg>
  );
}
