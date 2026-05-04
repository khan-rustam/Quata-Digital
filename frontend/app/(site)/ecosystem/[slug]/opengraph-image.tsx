import { getProduct } from "@/lib/ecosystem";
import { OG_SIZE, OG_CONTENT_TYPE, renderOg } from "@/lib/og-template";

export const alt = "QUATA product";
export const size = OG_SIZE;
export const contentType = OG_CONTENT_TYPE;

export default async function Image({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const product = getProduct(slug);
  return renderOg({
    eyebrow: product?.category ?? "Ecosystem",
    title: product?.name ?? "QUATA Product",
    tagline: product?.tagline ?? "Built on the QUATA rail.",
    pathname: `/ecosystem/${slug}`,
  });
}
