import type { Metadata } from "next";
import Link from "next/link";
import { CheckCircle2, AlertCircle } from "lucide-react";
import { apiUrl } from "@/lib/api";

export const metadata: Metadata = {
  title: "Unsubscribed",
  description: "You've been removed from the QUATA Digital newsletter.",
  robots: { index: false, follow: false },
};

type UnsubResponse = { ok: boolean; email?: string };

async function processUnsubscribe(email: string, token: string): Promise<UnsubResponse | null> {
  if (!email || !token) return null;
  try {
    const params = new URLSearchParams({ email, token });
    const res = await fetch(`${apiUrl}/newsletter/unsubscribe?${params.toString()}`, {
      method: "GET",
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as UnsubResponse;
  } catch {
    return null;
  }
}

export default async function UnsubscribePage({
  searchParams,
}: {
  searchParams: Promise<{ email?: string; token?: string }>;
}) {
  const { email, token } = await searchParams;
  const result = await processUnsubscribe(email ?? "", token ?? "");

  const success = !!result?.ok;

  return (
    <section className="container-page py-24 md:py-32">
      <div className="max-w-xl mx-auto text-center">
        {success ? (
          <>
            <div className="mx-auto inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700">
              <CheckCircle2 className="h-6 w-6" />
            </div>
            <div className="mt-6 text-xs uppercase tracking-wider text-muted-foreground">
              Newsletter
            </div>
            <h1 className="mt-3 text-3xl md:text-4xl font-semibold tracking-tight">
              You&apos;ve been unsubscribed.
            </h1>
            <p className="mt-4 text-muted-foreground">
              {result?.email ? (
                <>
                  We won&apos;t send any more newsletters to{" "}
                  <code className="font-mono text-foreground">{result.email}</code>.
                </>
              ) : (
                "You won't receive any more newsletter emails from QUATA Digital."
              )}
            </p>
            <p className="mt-3 text-sm text-muted-foreground">
              Changed your mind? You can re-subscribe from the footer of any page on{" "}
              <Link href="/" className="text-primary underline-offset-4 hover:underline">
                quatadigital.com
              </Link>
              .
            </p>
          </>
        ) : (
          <>
            <div className="mx-auto inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-amber-100 text-amber-700">
              <AlertCircle className="h-6 w-6" />
            </div>
            <div className="mt-6 text-xs uppercase tracking-wider text-muted-foreground">
              Newsletter
            </div>
            <h1 className="mt-3 text-3xl md:text-4xl font-semibold tracking-tight">
              We couldn&apos;t process that link.
            </h1>
            <p className="mt-4 text-muted-foreground">
              The unsubscribe link may be missing parameters or have expired. Open
              the most recent newsletter and use the link in its footer, or email{" "}
              <a
                href="mailto:info@quatadigital.com"
                className="text-primary underline-offset-4 hover:underline"
              >
                info@quatadigital.com
              </a>{" "}
              and we&apos;ll remove you manually.
            </p>
          </>
        )}
      </div>
    </section>
  );
}
