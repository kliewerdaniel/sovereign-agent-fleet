import type { Metadata } from "next";
import "./globals.css";
import { SiteNav } from "@/components/SiteNav";
import { LiveBanner } from "@/components/LiveBanner";

export const metadata: Metadata = {
  title: "Sovereign Agent Fleet — Live Trust Boundary",
  description:
    "Live control surface for a governed 3-agent fleet. Do not trust the model. Trust the execution protocol.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <div className="min-h-screen flex flex-col">
          <SiteNav />
          <LiveBanner />
          <main className="flex-1 max-w-7xl w-full mx-auto px-5 py-6">{children}</main>
          <footer className="border-t border-[var(--color-border)] px-5 py-4 text-xs faint">
            do not trust the model · trust the execution protocol · artifacts are signed &amp; hash-chained
          </footer>
        </div>
      </body>
    </html>
  );
}
