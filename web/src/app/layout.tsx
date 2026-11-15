import type { Metadata } from "next";
import { Inter, JetBrains_Mono, Unbounded } from "next/font/google";
import { Suspense } from "react";

import { TopBar } from "@/components/TopBar";
import { SpaceBackdrop } from "@/components/visuals";

import "./globals.css";

const unbounded = Unbounded({ subsets: ["latin"], weight: ["300", "400"], variable: "--font-unbounded" });
const inter = Inter({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-inter" });
const jetbrains = JetBrains_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-jetbrains" });

export const metadata: Metadata = {
  title: "Hestia — Guarding the flame beyond Earth",
  description: "AI-powered insights from NASA microgravity combustion experiments for Moon and Mars fire safety.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // suppressHydrationWarning: browser extensions add attributes to <html> before React loads
    // (e.g. webcrx); it only silences attribute mismatches on this one element.
    <html lang="en" suppressHydrationWarning className={`${unbounded.variable} ${inter.variable} ${jetbrains.variable} h-full`}>
      <body className="min-h-full">
        <SpaceBackdrop />
        <div className="sticky top-0 z-40 w-full border-b border-line bg-[var(--color-bg-glass)] backdrop-blur-md">
          <div className="mx-auto w-full max-w-[1440px] px-4 pt-3 pb-3 sm:px-6 lg:px-12 lg:pt-7 lg:pb-4">
            <Suspense>
              <TopBar />
            </Suspense>
          </div>
        </div>
        <div className="mx-auto flex min-h-screen w-full max-w-[1440px] flex-col px-6 pt-9 pb-10 lg:px-12">
          <main className="flex min-w-0 flex-1 flex-col">{children}</main>
        </div>
      </body>
    </html>
  );
}
