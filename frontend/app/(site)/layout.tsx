import { Suspense } from "react";
import { Navbar } from "@/components/site/navbar";
import { Footer } from "@/components/site/footer";
import { ToastProvider } from "@/components/ui/toast";
import { CookieBanner } from "@/components/site/cookie-banner";
import { ChatBubble } from "@/components/site/chat-bubble";
import { PageViewTracker } from "@/components/site/page-view-tracker";

// Server Component — Footer is `async` so it can fetch site-settings during
// SSR. Client-only children (CookieBanner, ChatBubble, PageViewTracker) are
// still client components on their own; they don't drag the layout with them.
export default function SiteLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ToastProvider>
      <Suspense fallback={null}>
        <PageViewTracker />
      </Suspense>
      <Navbar />
      <main className="flex-1">{children}</main>
      <Footer />
      <CookieBanner />
      <ChatBubble />
    </ToastProvider>
  );
}
