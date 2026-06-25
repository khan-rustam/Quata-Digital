/**
 * Commerce illustrations (88BASKET grocery + O3MALL marketplace).
 * Matches the payments.tsx flat product-mockup style: orange #FF6B00 +
 * Quata blue, neutral surfaces, embedded lucide glyphs, light tint bg.
 *
 * All landscape arts use a 4:3 viewBox (1200 x 900).
 */
import * as React from "react";
import {
  ShoppingBasket,
  ShoppingBag,
  Leaf,
  Carrot,
  Milk,
  Apple,
  Truck,
  Store,
  ShoppingCart,
  Star,
} from "lucide-react";
import { C } from "./palette";
import { Card, Pill, IconBadge, IconTile, AppWindow, ListRows, Dots, Blob } from "./kit";

const VB = "0 0 1200 900";

/** 88BASKET hero — online grocery marketplace, fresh produce + delivery. */
export function Grocery() {
  const products: { icon: typeof Leaf; bg: string; color: string; name: string; price: string }[] = [
    { icon: Apple, bg: C.orangeTint, color: C.orange, name: "Fresh fruit", price: "XAF 900" },
    { icon: Carrot, bg: C.greenSoft, color: C.green, name: "Veggies", price: "XAF 650" },
    { icon: Milk, bg: C.blueTint, color: C.blue, name: "Dairy", price: "XAF 1,200" },
    { icon: Leaf, bg: C.greenSoft, color: C.green, name: "Herbs", price: "XAF 400" },
    { icon: ShoppingBag, bg: C.orangeTint, color: C.orange, name: "Pantry", price: "XAF 2,100" },
    { icon: ShoppingBasket, bg: C.blueTint, color: C.blue, name: "Bundle", price: "XAF 5,000" },
  ];

  return (
    <svg viewBox={VB} width="100%" height="100%" preserveAspectRatio="xMidYMid meet" aria-hidden role="presentation">
      <rect x={0} y={0} width={1200} height={900} fill={C.orangeTint} />
      <Blob cx={260} cy={220} r={300} color={C.orangeSoft} opacity={0.55} />
      <Blob cx={1010} cy={760} r={300} color={C.blueSoft} opacity={0.7} />
      <Dots x={70} y={650} cols={9} rows={5} color={C.orange} opacity={0.16} />

      {/* Hero panel — big basket + brand */}
      <Card x={120} y={120} w={440} h={400} r={26}>
        <rect x={150} y={150} width={380} height={120} rx={20} fill={C.navy} />
        <text x={178} y={196} fontFamily="system-ui, sans-serif" fontSize={20} fill={C.blueSky} fontWeight={600}>88BASKET</text>
        <text x={178} y={240} fontFamily="system-ui, sans-serif" fontSize={32} fill={C.white} fontWeight={800}>Fresh groceries</text>
        <IconTile x={462} y={166} size={56} bg={C.orange} icon={ShoppingBag} color={C.white} iconScale={0.58} />

        {/* Big basket */}
        <circle cx={340} cy={390} r={92} fill={C.orangeTint} />
        <IconBadge cx={340} cy={390} r={84} bg={C.orange} icon={ShoppingBasket} color={C.white} iconScale={0.92} strokeWidth={2.1} />
        <IconBadge cx={430} cy={324} r={26} bg={C.green} icon={Leaf} iconScale={0.92} />
      </Card>

      {/* Product catalogue grid */}
      <Card x={596} y={120} w={486} h={400} r={26}>
        <text x={624} y={166} fontFamily="system-ui, sans-serif" fontSize={22} fill={C.ink} fontWeight={700}>Shop by category</text>
        <text x={624} y={196} fontFamily="system-ui, sans-serif" fontSize={16} fill={C.slate}>Same-day delivery in Bamenda</text>
        {products.map((p, i) => {
          const col = i % 3;
          const row = Math.floor(i / 3);
          const px = 624 + col * 150;
          const py = 220 + row * 138;
          return (
            <g key={i}>
              <rect x={px} y={py} width={130} height={120} rx={16} fill={C.panelSoft} stroke={C.line} strokeWidth={2} />
              <IconTile x={px + 18} y={py + 16} size={52} bg={p.bg} icon={p.icon} color={p.color} iconScale={0.58} />
              <text x={px + 84} y={py + 36} fontFamily="system-ui, sans-serif" fontSize={14} fill={C.ink} fontWeight={700}>{p.name}</text>
              <Pill x={px + 18} y={py + 84} w={94} h={22} fill={C.orangeTint} />
              <text x={px + 30} y={py + 100} fontFamily="system-ui, sans-serif" fontSize={13} fill={C.orangeDark} fontWeight={800}>{p.price}</text>
            </g>
          );
        })}
      </Card>

      {/* Delivery card */}
      <Card x={120} y={550} w={560} h={230} r={26}>
        <IconBadge cx={196} cy={636} r={48} bg={C.blue} icon={Truck} iconScale={0.96} />
        <text x={272} y={618} fontFamily="system-ui, sans-serif" fontSize={26} fill={C.ink} fontWeight={800}>Delivery</text>
        <text x={272} y={654} fontFamily="system-ui, sans-serif" fontSize={20} fill={C.slate}>Fresh, same-day fulfilment</text>
        <IconBadge cx={290} cy={702} r={20} bg={C.greenSoft} icon={Leaf} iconScale={0.9} />
        <Pill x={318} y={690} w={150} h={24} fill={C.panelMute} />

        {/* status track */}
        <rect x={272} y={736} width={356} height={10} rx={5} fill={C.panelMute} />
        <rect x={272} y={736} width={250} height={10} rx={5} fill={C.orange} />
        <circle cx={522} cy={741} r={9} fill={C.orange} />
        <text x={482} y={618} fontFamily="system-ui, sans-serif" fontSize={18} fill={C.green} fontWeight={700}>On the way</text>
      </Card>

      {/* Vendor chip card */}
      <Card x={700} y={550} w={382} h={230} r={26} fill={C.navy} stroke={C.navy}>
        <IconBadge cx={760} cy={616} r={36} bg={C.orange} icon={Store} iconScale={1.0} />
        <text x={812} y={602} fontFamily="system-ui, sans-serif" fontSize={22} fill={C.white} fontWeight={700}>Local vendors</text>
        <text x={812} y={636} fontFamily="system-ui, sans-serif" fontSize={17} fill={C.blueSky}>Markets · farms · shops</text>
        {[0, 1, 2].map((i) => (
          <g key={i}>
            <rect x={730} y={672 + i * 1} width={0} height={0} />
            <rect x={730 + i * 116} y={680} width={104} height={64} rx={14} fill={C.navyDeep} />
            <IconBadge cx={760 + i * 116} cy={712} r={18} bg={i === 0 ? C.orange : C.blue} icon={i === 2 ? Leaf : Store} iconScale={0.9} />
            <rect x={786 + i * 116} y={704} width={40} height={8} rx={4} fill={C.blueSoft} opacity={0.5} />
            <rect x={786 + i * 116} y={720} width={28} height={7} rx={3.5} fill={C.blueSoft} opacity={0.3} />
          </g>
        ))}
      </Card>
    </svg>
  );
}

/** O3MALL hero — multi-vendor ecommerce storefront + catalogue + cart. */
export function Marketplace() {
  const ratingDots = (cx: number, cy: number, filled: number) =>
    [0, 1, 2, 3, 4].map((i) => (
      <g key={i} transform={`translate(${cx + i * 18} ${cy})`}>
        <Star width={13} height={13} color={i < filled ? C.gold : C.line} fill={i < filled ? C.gold : C.panel} strokeWidth={2} />
      </g>
    ));

  const catalogue = [
    { price: "XAF 12,500", stars: 5, accent: C.orangeTint },
    { price: "XAF 8,900", stars: 4, accent: C.blueTint },
    { price: "XAF 24,000", stars: 5, accent: C.greenSoft },
    { price: "XAF 6,400", stars: 4, accent: C.goldSoft },
  ];

  return (
    <svg viewBox={VB} width="100%" height="100%" preserveAspectRatio="xMidYMid meet" aria-hidden role="presentation">
      <rect x={0} y={0} width={1200} height={900} fill={C.blueTint} />
      <Blob cx={1000} cy={200} r={300} color={C.orangeSoft} opacity={0.5} />
      <Blob cx={220} cy={760} r={280} color={C.blueSoft} opacity={0.7} />
      <Dots x={70} y={650} cols={9} rows={5} color={C.blue} opacity={0.16} />

      {/* Browser storefront */}
      <AppWindow x={100} y={110} w={760} h={680} title="o3mall" accent={C.orange}>
        {/* search + brand strip */}
        <rect x={132} y={172} width={200} height={36} rx={18} fill={C.orange} />
        <g transform="translate(150 180)"><Store width={20} height={20} color={C.white} strokeWidth={2.2} /></g>
        <text x={180} y={196} fontFamily="system-ui, sans-serif" fontSize={18} fill={C.white} fontWeight={800}>O3MALL</text>
        <rect x={348} y={172} width={386} height={36} rx={18} fill={C.panelSoft} stroke={C.line} strokeWidth={2} />
        <text x={372} y={196} fontFamily="system-ui, sans-serif" fontSize={15} fill={C.steel}>Search storefronts in Bamenda</text>

        {/* Multi-vendor sidebar */}
        <text x={132} y={252} fontFamily="system-ui, sans-serif" fontSize={15} fill={C.slate} fontWeight={700}>Vendor stores</text>
        <ListRows x={132} y={266} w={216} rows={5} rowH={86} gap={14} lead={C.orangeTint} tag="open" />
        {/* store glyphs over the list leads */}
        {[0, 1, 2, 3, 4].map((i) => (
          <g key={i} transform={`translate(${132 + 43} ${266 + 43 + i * 100})`}>
            <Store width={22} height={22} color={i % 2 ? C.blue : C.orange} strokeWidth={2.2} />
          </g>
        ))}

        {/* Product catalogue grid */}
        <text x={376} y={252} fontFamily="system-ui, sans-serif" fontSize={15} fill={C.slate} fontWeight={700}>Featured products</text>
        {catalogue.map((p, i) => {
          const col = i % 2;
          const row = Math.floor(i / 2);
          const px = 376 + col * 184;
          const py = 266 + row * 232;
          return (
            <g key={i}>
              <rect x={px} y={py} width={168} height={208} rx={16} fill={C.panel} stroke={C.line} strokeWidth={2} />
              {/* image block */}
              <rect x={px + 14} y={py + 14} width={140} height={92} rx={12} fill={p.accent} />
              <g transform={`translate(${px + 64} ${py + 38})`}>
                <ShoppingBag width={44} height={44} color={i % 3 === 0 ? C.orange : C.blue} strokeWidth={2} />
              </g>
              {/* title bars */}
              <rect x={px + 14} y={py + 122} width={120} height={9} rx={4.5} fill={C.panelMute} />
              <rect x={px + 14} y={py + 138} width={80} height={8} rx={4} fill={C.lineSoft} />
              {/* rating dots */}
              {ratingDots(px + 16, py + 156, p.stars)}
              {/* price */}
              <text x={px + 14} y={py + 196} fontFamily="system-ui, sans-serif" fontSize={17} fill={C.orangeDark} fontWeight={800}>{p.price}</text>
            </g>
          );
        })}
      </AppWindow>

      {/* Floating cart card */}
      <Card x={812} y={300} w={300} h={320} r={26}>
        <IconBadge cx={862} cy={358} r={34} bg={C.orange} icon={ShoppingCart} iconScale={1.0} />
        <text x={910} y={350} fontFamily="system-ui, sans-serif" fontSize={22} fill={C.ink} fontWeight={800}>Your cart</text>
        <text x={910} y={380} fontFamily="system-ui, sans-serif" fontSize={18} fill={C.green} fontWeight={700}>3 items</text>

        {/* cart rows */}
        {[0, 1, 2].map((i) => (
          <g key={i}>
            <rect x={836} y={414 + i * 52} width={252} height={42} rx={12} fill={C.panelSoft} stroke={C.lineSoft} strokeWidth={2} />
            <rect x={848} y={424 + i * 52} width={22} height={22} rx={6} fill={i === 0 ? C.orangeTint : C.blueTint} />
            <rect x={884} y={428 + i * 52} width={90} height={8} rx={4} fill={C.panelMute} />
            <text x={1012} y={440 + i * 52} fontFamily="system-ui, sans-serif" fontSize={13} fill={C.slate} fontWeight={700}>XAF {i === 0 ? "12.5k" : i === 1 ? "8.9k" : "6.4k"}</text>
          </g>
        ))}

        {/* Checkout button */}
        <Pill x={836} y={578} w={252} h={30} fill={C.orange} />
        <text x={962} y={599} textAnchor="middle" fontFamily="system-ui, sans-serif" fontSize={17} fill={C.white} fontWeight={800}>Checkout</text>
      </Card>
    </svg>
  );
}
