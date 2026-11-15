"use client";

import { Bell, Flame, Search } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { openSearch } from "@/components/CommandPalette";
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
    <header className="flex flex-wrap items-center justify-between gap-x-4 gap-y-3">
      <Link href="/" className="order-1 flex items-center gap-3" aria-label="Hestia home">
        <span className="flex size-9 items-center justify-center rounded-full border border-line-strong">
          <Flame aria-hidden size={18} strokeWidth={1.75} className="text-ember" />
        </span>
        <span className="font-display text-[18px] tracking-[0.4em] text-fg">HESTIA</span>
      </Link>

      <nav aria-label="Main" className="glass order-3 flex w-full max-w-full gap-1 overflow-x-auto rounded-full p-1.5 lg:order-2 lg:w-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {NAV.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active(item.href) ? "page" : undefined}
            className={cx(
              "rounded-full border px-3 py-1.5 text-[13px] leading-normal whitespace-nowrap transition sm:px-4 sm:py-2 sm:text-[14px]",
              active(item.href) ? "border-line bg-raised font-medium text-fg" : "border-transparent text-fg-2 hover:text-fg",
            )}
          >
            {item.label}
          </Link>
        ))}
      </nav>

      <div className="order-2 flex items-center gap-2 sm:gap-3 lg:order-3">
        <IconButton icon={Search} label="Search (Ctrl/⌘ K)" onClick={openSearch} />
        <span className="hidden sm:contents"><IconButton icon={Bell} label="Notifications" /></span>
        <span className="glass flex items-center gap-2 rounded-full p-1.5 md:pr-3.5">
          <span aria-hidden className="size-8 rounded-full bg-[linear-gradient(135deg,#FF7A30,#5AA9FF)]" />
          <span className="t-mono-m hidden text-fg-2 md:inline">black-vortex</span>
        </span>
      </div>
    </header>
  );
}
