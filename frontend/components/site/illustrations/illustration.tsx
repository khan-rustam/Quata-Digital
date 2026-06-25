/**
 * <Illustration> — drop-in replacement for <BrandImage> that renders a custom,
 * on-brand SVG illustration inside a clean framed figure. Pick the artwork by
 * `name` (see REGISTRY). Pure Server Component — no client JS.
 *
 * Every illustration is topical to the page/section it sits in, so a visitor
 * understands the content from the image alone (the image-relevance brief).
 */
import * as React from "react";
import { cn } from "@/lib/utils";

import { PaymentsApp, MerchantPayment, PosTerminal } from "./payments";
import {
  TeamCollab,
  TeamCareers,
  PortraitFounder,
  PortraitBusiness,
  PortraitExec,
  PortraitInvestor,
  PortraitEngineer,
  SupportAgent,
  Boardroom,
  Meeting,
  Developer,
  OfficeHQ,
} from "./people";
import { BusinessOps, DeliveryRider } from "./logistics";
import { FoodDelivery } from "./food";
import { Grocery, Marketplace } from "./commerce";
import { RealEstate } from "./realestate";
import { Telemedicine } from "./health";
import { GrowthCharts, AnalyticsLaptop } from "./analytics";

const REGISTRY = {
  // About / Careers
  "about-hero": TeamCollab,
  "about-founder": PortraitFounder,
  "careers-hero": TeamCareers,

  // Contact
  "contact-hero": SupportAgent,
  "contact-office": OfficeHQ,

  // Partners — Business
  "partner-business-hero": MerchantPayment,
  "partner-business-sidebar": PosTerminal,
  "partner-business-faq": PortraitBusiness,

  // Partners — Strategic
  "partner-strategic-hero": Boardroom,
  "partner-strategic-sidebar": Meeting,
  "partner-strategic-faq": PortraitExec,

  // Partners — Investor
  "partner-investor-hero": GrowthCharts,
  "partner-investor-sidebar": AnalyticsLaptop,
  "partner-investor-faq": PortraitInvestor,

  // Partners — Service
  "partner-service-hero": DeliveryRider,
  "partner-service-sidebar": Developer,
  "partner-service-faq": PortraitEngineer,

  // Ecosystem products
  "product-quatapay": PaymentsApp,
  "product-abaqwa": BusinessOps,
  "product-quatafood": FoodDelivery,
  "product-88basket": Grocery,
  "product-88brickz": RealEstate,
  "product-o3mall": Marketplace,
  "product-qmediq": Telemedicine,
} satisfies Record<string, React.ComponentType>;

export type IllustrationName = keyof typeof REGISTRY;

export function Illustration({
  name,
  alt,
  width,
  height,
  rounded = "rounded-3xl",
  className,
  caption,
  frame = true,
}: {
  name: IllustrationName;
  /** Describes the artwork for assistive tech (the figure is role="img"). */
  alt: string;
  width: number;
  height: number;
  rounded?: string;
  className?: string;
  caption?: string;
  /** Set false to render the bare SVG with no card frame. */
  frame?: boolean;
}) {
  const Art = REGISTRY[name];

  return (
    <figure className={cn("relative", className)}>
      <div
        role="img"
        aria-label={alt}
        className={cn(
          "relative w-full overflow-hidden",
          frame && "border border-border bg-card ring-soft",
          rounded,
        )}
        style={{ aspectRatio: `${width} / ${height}` }}
      >
        <div className="absolute inset-0">
          <Art />
        </div>
      </div>
      {caption && (
        <figcaption className="mt-3 text-xs text-muted-foreground">{caption}</figcaption>
      )}
    </figure>
  );
}
