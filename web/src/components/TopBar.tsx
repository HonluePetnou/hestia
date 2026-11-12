"use client";

import { Bell, Flame, Search } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { IconButton, cx } from "@/components/ui";

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/experiments", label: "Experiments" },
  { href: "/compare", label: "Compare" },
  { href: "/relevance", label: "Relevance" },
  { href: "/assistant", label: "Assistant" },
  { href: "/simulator", label: "Simulator" },
];

export function TopBar() {
  const pathname = usePathname();
  const active = (href: string) => (href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`));

  return (
    <header className="flex flex-wrap items-center justify-between gap-4">
      <Link href="/" className="flex items-center gap-3" aria-label="Hestia home">
        <span className="flex size-9 items-center justify-center rounded-full border border-line-strong">
          <Flame aria-hidden size={18} strokeWidth={1.75} className="text-ember" />
        </span>
        <span className="font-display text-[18px] tracking-[0.4em] text-fg">HESTIA</span>
      </Link>

      <nav aria-label="Main" className="glass flex max-w-full gap-1 overflow-x-auto rounded-full p-1.5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {NAV.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active(item.href) ? "page" : undefined}
            className={cx(
              "rounded-full border px-4 py-2 text-[14px] leading-normal whitespace-nowrap transition",
              active(item.href) ? "border-line bg-raised font-medium text-fg" : "border-transparent text-fg-2 hover:text-fg",
            )}
          >
            {item.label}
          </Link>
        ))}
      </nav>

      <div className="flex items-center gap-3">
        <IconButton icon={Search} label="Search" href="/experiments" />
        <IconButton icon={Bell} label="Notifications" />
        <span className="glass flex items-center gap-2 rounded-full py-1.5 pr-3.5 pl-1.5">
          <span aria-hidden className="size-8 rounded-full bg-[linear-gradient(135deg,#FF7A30,#5AA9FF)]" />
          <span className="t-mono-m text-fg-2">black-vortex</span>
        </span>
      </div>
    </header>
  );
}
