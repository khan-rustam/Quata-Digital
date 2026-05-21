import { Suspense } from "react";
import type { Metadata } from "next";
import SearchClient from "./SearchClient";

export const metadata: Metadata = {
  title: "Search",
  description: "Search across QUATA's products, news and open roles.",
};

// The page shell is static — the SearchClient does the actual query
// reading from `useSearchParams()` inside the Suspense boundary, so we
// don't need `force-dynamic` and the empty shell can be edge-cached.

export default function SearchPage() {
  return (
    <Suspense fallback={null}>
      <SearchClient />
    </Suspense>
  );
}
