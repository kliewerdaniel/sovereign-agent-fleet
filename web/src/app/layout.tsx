import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { SiteNav } from "@/components/SiteNav";
import { ChainIntegrityBanner } from "@/components/ChainIntegrityBanner";
import { fetchChainIntegrity } from "@/lib/fleet";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Sovereign Agent Fleet — Control Surface",
  description:
    "Trust-boundary-first operator surface over the Sovereign Agent Fleet. Do not trust the model. Trust the execution protocol.",
};

export default async function RootLayout({
  children,
}: LayoutProps<"/">) {
  let integrity;
  try {
    integrity = await fetchChainIntegrity();
  } catch {
    integrity = null;
  }
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        {integrity ? (
          <ChainIntegrityBanner integrity={integrity} />
        ) : (
          <div className="trust-boundary w-full px-4 py-1.5 text-xs bg-[var(--color-warn-dim)] text-[var(--color-warn)] mono">
            ⚠ bridge unreachable — chain state unknown
          </div>
        )}
        <SiteNav />
        <main className="flex-1">{children}</main>
        <footer className="trust-boundary px-4 py-2 text-[0.65rem] text-[var(--color-ink-faint)] mono">
          do not trust the model · trust the execution protocol · artifacts are
          signed &amp; hash-chained
        </footer>
      </body>
    </html>
  );
}
