"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/experiments", label: "Experiment Explorer" },
  { href: "/compare", label: "Compare" },
  { href: "/relevance", label: "Moon & Mars Relevance" },
  { href: "/assistant", label: "AI Assistant" },
  { href: "/simulator", label: "3D Simulator" },
];

export function Sidebar() {
  const pathname = usePathname();
  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);

  return (
    <nav className="flex w-56 shrink-0 flex-col gap-1 border-r border-gray-200 p-4">
      <Link href="/" className="mb-4 text-xl font-semibold">
        Hestia
      </Link>
      {NAV.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          aria-current={isActive(item.href) ? "page" : undefined}
          className="rounded px-2 py-1 text-sm hover:bg-gray-100 aria-[current=page]:bg-gray-200 aria-[current=page]:font-medium"
        >
          {item.label}
        </Link>
      ))}
    </nav>
  );
}
