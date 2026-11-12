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
    <html lang="en" className={`${unbounded.variable} ${inter.variable} ${jetbrains.variable} h-full`}>
      <body className="min-h-full">
        <SpaceBackdrop />
        <div className="mx-auto flex min-h-screen w-full max-w-[1440px] flex-col gap-9 px-6 pt-7 pb-10 lg:px-12">
          <Suspense>
            <TopBar />
          </Suspense>
          <main className="flex flex-1 flex-col">{children}</main>
        </div>
      </body>
    </html>
  );
}
