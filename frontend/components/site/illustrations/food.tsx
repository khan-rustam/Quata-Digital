/**
 * Food illustrations (QUATAFOOD — food ordering + delivery).
 * Matches the shared flat product-mockup style: orange #FF6B00 + Quata blue,
 * neutral surfaces, embedded lucide glyphs, African skin tones for people.
 *
 * All landscape arts use a 4:3 viewBox (1200 x 900).
 */
import * as React from "react";
import {
  UtensilsCrossed,
  ChefHat,
  Store,
  CheckCircle2,
  Bike,
  Clock,
} from "lucide-react";
import { C } from "./palette";
import { Card, IconBadge, IconTile, Phone, ListRows, Route, Pin, Dots, Blob, Person } from "./kit";

const VB = "0 0 1200 900";

/** QUATAFOOD hero — phone food-order screen + rider with food bag + tracking. */
export function FoodDelivery() {
  return (
    <svg viewBox={VB} width="100%" height="100%" preserveAspectRatio="xMidYMid meet" aria-hidden role="presentation">
      <rect x={0} y={0} width={1200} height={900} fill={C.orangeTint} />
      <Blob cx={250} cy={210} r={300} color={C.orangeSoft} opacity={0.55} />
      <Blob cx={1010} cy={760} r={300} color={C.blueSoft} opacity={0.7} />
      <Dots x={70} y={650} cols={9} rows={4} color={C.orange} opacity={0.16} />

      {/* Phone — restaurant menu + order placed */}
      <Phone x={140} y={120} w={420} h={660}>
        {/* restaurant header */}
        <rect x={160} y={150} width={380} height={120} rx={20} fill={C.navy} />
        <IconTile x={476} y={166} size={44} bg={C.orange} icon={ChefHat} color={C.white} iconScale={0.58} />
        <text x={186} y={196} fontFamily="system-ui, sans-serif" fontSize={20} fill={C.blueSky} fontWeight={600}>QUATAFOOD · Bamenda</text>
        <text x={186} y={238} fontFamily="system-ui, sans-serif" fontSize={30} fill={C.white} fontWeight={800}>Mama Africa Grill</text>

        {/* menu rows with XAF prices */}
        <ListRows x={160} y={296} w={380} rows={3} rowH={62} gap={14} lead={C.orangeSoft} />
        <text x={490} y={335} fontFamily="system-ui, sans-serif" fontSize={17} fill={C.orange} fontWeight={800} textAnchor="end">XAF 3,500</text>
        <text x={490} y={411} fontFamily="system-ui, sans-serif" fontSize={17} fill={C.orange} fontWeight={800} textAnchor="end">XAF 2,000</text>
        <text x={490} y={487} fontFamily="system-ui, sans-serif" fontSize={17} fill={C.orange} fontWeight={800} textAnchor="end">XAF 4,200</text>

        {/* dish glyphs over the leading discs */}
        <g transform="translate(178 313)"><UtensilsCrossed width={28} height={28} color={C.orangeDark} strokeWidth={2.2} /></g>
        <g transform="translate(178 389)"><UtensilsCrossed width={28} height={28} color={C.orangeDark} strokeWidth={2.2} /></g>
        <g transform="translate(178 465)"><UtensilsCrossed width={28} height={28} color={C.orangeDark} strokeWidth={2.2} /></g>

        {/* Order placed chip */}
        <rect x={160} y={536} width={380} height={108} rx={18} fill={C.greenSoft} />
        <IconBadge cx={206} cy={590} r={28} bg={C.green} icon={CheckCircle2} iconScale={1.05} />
        <text x={250} y={580} fontFamily="system-ui, sans-serif" fontSize={22} fill={C.ink} fontWeight={700}>Order placed</text>
        <text x={250} y={612} fontFamily="system-ui, sans-serif" fontSize={18} fill={C.slate}>Total · XAF 9,700</text>
        <g transform="translate(486 570)"><Clock width={26} height={26} color={C.green} strokeWidth={2.4} /></g>
      </Phone>

      {/* Order tracking card — dashed route + pin + ETA */}
      <Card x={612} y={150} w={470} h={300} r={22}>
        <IconBadge cx={668} cy={208} r={32} bg={C.blue} icon={Bike} iconScale={1.0} />
        <text x={714} y={196} fontFamily="system-ui, sans-serif" fontSize={24} fill={C.ink} fontWeight={700}>On the way</text>
        <text x={714} y={228} fontFamily="system-ui, sans-serif" fontSize={19} fill={C.slate}>Rider · Emmanuel</text>

        {/* map area */}
        <rect x={636} y={258} width={422} height={168} rx={16} fill={C.blueTint} stroke={C.line} strokeWidth={2} />
        <Route d="M676 392 C 760 300, 860 420, 960 300" color={C.orange} width={5} />
        <IconBadge cx={676} cy={392} r={14} bg={C.navy} icon={Store} color={C.white} iconScale={0.95} strokeWidth={2.2} />
        <Pin cx={960} cy={312} size={40} color={C.orange} />
      </Card>

      {/* ETA pill card */}
      <Card x={612} y={470} w={222} h={148} r={22}>
        <g transform="translate(636 502)"><Clock width={30} height={30} color={C.blue} strokeWidth={2.4} /></g>
        <text x={636} y={566} fontFamily="system-ui, sans-serif" fontSize={18} fill={C.slate} fontWeight={600}>Arriving in</text>
        <text x={636} y={600} fontFamily="system-ui, sans-serif" fontSize={30} fill={C.orange} fontWeight={800}>12 min</text>
      </Card>

      {/* Restaurant storefront hint card */}
      <Card x={852} y={470} w={230} h={148} r={22} fill={C.navy} stroke={C.navy}>
        <IconBadge cx={908} cy={530} r={30} bg={C.orange} icon={Store} iconScale={1.0} />
        <text x={876} y={584} fontFamily="system-ui, sans-serif" fontSize={18} fill={C.white} fontWeight={700}>120+ kitchens</text>
        <text x={876} y={606} fontFamily="system-ui, sans-serif" fontSize={15} fill={C.blueSky}>Local restaurants</text>
      </Card>

      {/* Delivery rider with insulated food bag */}
      <g>
        {/* food bag (square, behind shoulder) */}
        <rect x={918} y={640} width={120} height={120} rx={18} fill={C.orange} />
        <rect x={918} y={640} width={120} height={120} rx={18} fill="none" stroke={C.orangeDark} strokeWidth={3} />
        <rect x={918} y={640} width={120} height={30} rx={12} fill={C.orangeDark} />
        <rect x={960} y={624} width={36} height={20} rx={8} fill={C.orangeDark} />
        <IconBadge cx={978} cy={712} r={30} bg={C.white} icon={UtensilsCrossed} color={C.orange} iconScale={1.05} strokeWidth={2.4} />
      </g>
      <g transform="translate(770 470)">
        <Person cx={0} topY={0} scale={1.15} skin={C.skin3} shirt={C.blue} accessory={
          <g transform="translate(-44 -86)"><Bike width={36} height={36} color={C.white} strokeWidth={2.4} /></g>
        } />
      </g>

      <Dots x={120} y={830} cols={14} rows={1} color={C.navy} opacity={0.18} />
    </svg>
  );
}
