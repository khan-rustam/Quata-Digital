/**
 * Maps a product feature (by its title/body text) to the most relevant lucide
 * icon, so every feature card carries a topical glyph — per the image-relevance
 * brief ("every feature section must use images relevant to that feature").
 *
 * Keyword-matched so it stays correct as the ecosystem copy evolves, with a
 * sensible default. Returns a LucideIcon component.
 */
import {
  type LucideIcon,
  CreditCard,
  Wallet,
  QrCode,
  BarChart3,
  TrendingUp,
  Code2,
  ShieldCheck,
  Bike,
  Truck,
  Package,
  UtensilsCrossed,
  Building2,
  Home,
  Store,
  Stethoscope,
  HeartPulse,
  CalendarClock,
  ShoppingBasket,
  ShoppingCart,
  Layers,
  Bell,
  Mail,
  Headphones,
  Banknote,
  Receipt,
  Users,
  RefreshCw,
  Lock,
  MapPin,
  Sparkles,
} from "lucide-react";

const RULES: [RegExp, LucideIcon][] = [
  [/qr|payment link|\blink\b/i, QrCode],
  [/settle|settlement|payout|deposit|withdraw|transfer|mobile money|momo|\bwallet\b/i, Wallet],
  [/card|checkout|multi-?channel|acceptance|\baccept\b|gateway/i, CreditCard],
  [/escrow|hold|secur|fraud|risk|compliance|\bkyc\b|\bkyb\b|verif/i, ShieldCheck],
  [/reliab|uptime|idempoten|guard|duplicate/i, RefreshCw],
  [/api|developer|webhook|\bsdk\b|integrat/i, Code2],
  [/dashboard|report|analytic|insight|metric|visibility|track/i, BarChart3],
  [/growth|scale|expansion|volume/i, TrendingUp],
  [/rider|courier|dispatch|delivery|last-?mile|parcel|shipping/i, Bike],
  [/logistic|fleet|route/i, Truck],
  [/inventory|stock|catalog/i, Package],
  [/menu|restaurant|kitchen|food|dish/i, UtensilsCrossed],
  [/rent|landlord|tenant|lease|property|real ?estate/i, Building2],
  [/house|apartment|listing|home/i, Home],
  [/vendor|marketplace|storefront|\bshop\b|\bstore\b|merchant/i, Store],
  [/grocery|basket|fresh|produce|essential/i, ShoppingBasket],
  [/\bcart\b|\border\b/i, ShoppingCart],
  [/doctor|patient|consult|clinic|prescription|\blab\b|medical|telemedic|pharmac/i, Stethoscope],
  [/health|care|wellness/i, HeartPulse],
  [/appointment|schedul|booking|calendar/i, CalendarClock],
  [/notification|\bsms\b|email|push|campaign|message/i, Bell],
  [/newsletter|inbox/i, Mail],
  [/support|help|agent|service desk/i, Headphones],
  [/fee|revenue|commission|pricing|payment/i, Banknote],
  [/receipt|invoice|billing/i, Receipt],
  [/team|staff|customer|user|agent network|community/i, Users],
  [/split|escrow|multi-?vendor|orchestrat/i, Layers],
  [/identity|login|auth|access|privacy/i, Lock],
  [/coverage|region|location|map|nationwide/i, MapPin],
];

export function featureIcon(title: string, body = ""): LucideIcon {
  const text = `${title} ${body}`;
  for (const [re, icon] of RULES) {
    if (re.test(text)) return icon;
  }
  return Sparkles;
}
