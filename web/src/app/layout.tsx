import type { Metadata } from "next";
import { Suspense } from "react";

import { Sidebar } from "@/components/Sidebar";

import "./globals.css";

export const metadata: Metadata = {
  title: "Hestia — Guarding the flame beyond Earth",
  description: "AI-powered insights from NASA microgravity combustion experiments.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full">
      <body className="flex min-h-full bg-white text-gray-900">
        <Suspense>
          <Sidebar />
        </Suspense>
        <main className="min-w-0 flex-1 p-6">{children}</main>
      </body>
    </html>
  );
}
