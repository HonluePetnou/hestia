"use client";

import { ChevronDown, Search } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState, useTransition } from "react";

import { Segmented, cx } from "@/components/ui";

const FUELS = ["n-heptane", "methanol", "PMMA", "cotton-fiberglass", "SIBAL cotton-fiberglass", "Nomex", "Teflon", "ethylene"];
const GRAVITY = [
  { value: "", label: "Any" },
  { value: "microgravity", label: "Micro-g" },
  { value: "lunar", label: "Lunar" },
  { value: "martian", label: "Martian" },
  { value: "earth", label: "Earth" },
];
const OUTCOMES = [
  { value: "spread", label: "Spread", dot: "bg-ember", text: "text-ember" },
  { value: "extinction", label: "Extinction", dot: "bg-data", text: "text-data" },
  { value: "complete_burn", label: "Complete burn", dot: "bg-fg-3", text: "text-fg-2" },
];
const O2_MIN = 10, O2_MAX = 40;

export function SearchBox() {
  const params = useSearchParams();
  const update = useUpdate();
  return (
    <label className="glass flex w-full max-w-[380px] items-center gap-2.5 rounded-full px-4.5 py-3">
      <Search aria-hidden size={16} strokeWidth={1.75} className="text-fg-3" />
      <span className="sr-only">Search experiments</span>
      <input
        type="search"
        defaultValue={params.get("q") ?? ""}
        placeholder="Search experiments, fuels, NTRS reports…"
        onChange={(e) => update({ q: e.target.value })}
        className="t-body-s min-w-0 flex-1 bg-transparent text-fg outline-none placeholder:text-fg-3"
      />
      <kbd className="t-mono-s rounded-sm border border-line-strong px-1.5 py-0.5 text-fg-3">⌘K</kbd>
    </label>
  );
}

function useUpdate() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [, start] = useTransition();
  return (patch: Record<string, string | null>) => {
    const next = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(patch)) {
      if (v === null || v === "") next.delete(k);
      else next.set(k, v);
    }
    start(() => router.replace(`${pathname}${next.size ? `?${next}` : ""}`, { scroll: false }));
  };
}

export function FilterBar() {
  const params = useSearchParams();
  const update = useUpdate();
  const [o2, setO2] = useState<[number, number]>([
    Number(params.get("o2_min") ?? O2_MIN),
    Number(params.get("o2_max") ?? O2_MAX),
  ]);
  const commitO2 = () =>
    update({ o2_min: o2[0] > O2_MIN ? String(o2[0]) : null, o2_max: o2[1] < O2_MAX ? String(o2[1]) : null });
  const pct = (v: number) => ((v - O2_MIN) / (O2_MAX - O2_MIN)) * 100;
  const outcome = params.get("outcome");

  return (
    <div className="glass flex flex-wrap items-center justify-between gap-x-5 gap-y-3 rounded-[28px] px-5 py-2.5 xl:flex-nowrap xl:rounded-full">
      <label className="flex min-w-0 max-w-full items-center gap-2.5 xl:shrink-0">
        <span className="t-caps-s text-fg-3">Fuel</span>
        <span className="relative flex items-center">
          <select
            value={params.get("fuel") ?? ""}
            onChange={(e) => update({ fuel: e.target.value })}
            className="w-[150px] appearance-none truncate rounded-full border border-line bg-raised py-[6px] pr-8 pl-3.5 text-[13px] text-fg outline-none focus-visible:border-ember"
          >
            <option value="">All fuels</option>
            {FUELS.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
          <ChevronDown aria-hidden size={14} className="pointer-events-none absolute right-3 text-fg-2" />
        </span>
      </label>

      <div className="flex min-w-0 max-w-full items-center gap-2.5 xl:shrink-0">
        <span className="t-caps-s text-fg-3">Gravity</span>
        <Segmented size="sm" className="min-w-0 overflow-x-auto [scrollbar-width:none]" label="Gravity" options={GRAVITY} value={params.get("gravity") ?? ""} onChange={(v) => update({ gravity: v })} />
      </div>

      <div className="flex min-w-0 max-w-full items-center gap-2.5 xl:shrink-0">
        <span className="t-caps-s text-fg-3">Outcome</span>
        <div className="flex flex-wrap gap-2">
          {OUTCOMES.map((o) => {
            const on = outcome === o.value;
            return (
              <button
                key={o.value}
                type="button"
                aria-pressed={on}
                onClick={() => update({ outcome: on ? null : o.value })}
                className={cx("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1.5 whitespace-nowrap transition", on ? "border-ember-line bg-ember-tint" : "border-line bg-glass hover:border-line-strong")}
              >
                <span className={cx("size-1.5 rounded-full", o.dot)} />
                <span className={cx("t-caps-s", o.text)}>{o.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex min-w-0 max-w-full items-center gap-2.5 xl:shrink-0">
        <span className="t-caps-s text-fg-3">O₂</span>
        <div
          className="range-dual w-[90px] rounded-full"
          style={{ background: `linear-gradient(to right, var(--color-bg-surface-raised) ${pct(o2[0])}%, var(--color-accent-default) ${pct(o2[0])}% ${pct(o2[1])}%, var(--color-bg-surface-raised) ${pct(o2[1])}%) center / 100% 4px no-repeat` }}
        >
          <input
            type="range" className="range" aria-label="Minimum oxygen %" min={O2_MIN} max={O2_MAX} value={o2[0]}
            onChange={(e) => setO2([Math.min(Number(e.target.value), o2[1] - 1), o2[1]])}
            onPointerUp={commitO2} onKeyUp={commitO2}
          />
          <input
            type="range" className="range" aria-label="Maximum oxygen %" min={O2_MIN} max={O2_MAX} value={o2[1]}
            onChange={(e) => setO2([o2[0], Math.max(Number(e.target.value), o2[0] + 1)])}
            onPointerUp={commitO2} onKeyUp={commitO2}
          />
        </div>
        <span className="t-mono-s w-[56px] text-fg">{o2[0]}–{o2[1]}%</span>
        {/* Kept with the O₂ group so it never wraps onto a line of its own */}
        <button
          type="button"
          onClick={() => { setO2([O2_MIN, O2_MAX]); update({ fuel: null, gravity: null, outcome: null, o2_min: null, o2_max: null, q: null }); }}
          className="t-body-s border-l border-line pl-3 text-ember hover:text-ember-soft"
        >
          Reset
        </button>
      </div>
    </div>
  );
}
