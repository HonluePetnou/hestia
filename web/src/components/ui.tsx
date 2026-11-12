/** Minimal, unstyled-by-design building blocks. Restyle freely once the Figma design lands. */
import type { ReactNode } from "react";

import { ApiError } from "@/lib/api";

export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <header className="mb-6">
      <h1 className="text-2xl font-semibold">{title}</h1>
      {subtitle && <p className="text-sm text-gray-600">{subtitle}</p>}
    </header>
  );
}

export function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mb-6">
      <h2 className="mb-2 text-lg font-medium">{title}</h2>
      {children}
    </section>
  );
}

export function Json({ data }: { data: unknown }) {
  return (
    <pre className="overflow-auto rounded border border-gray-200 bg-gray-50 p-3 text-xs">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}

export function Loading() {
  return <p className="text-sm text-gray-500">Loading…</p>;
}

export function ErrorBox({ error }: { error: unknown }) {
  const message =
    error instanceof ApiError || error instanceof Error ? error.message : String(error);
  return (
    <div role="alert" className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-800">
      {message}
    </div>
  );
}
