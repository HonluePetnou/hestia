"use client";

import { ArrowUpRight, FileText, FlaskConical, Flame, Lightbulb, Search, Sparkles, type LucideIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { cx } from "@/components/ui";
import { api, type Schemas } from "@/lib/api";

/** Opens the palette from anywhere (the top bar's search button dispatches this). */
export const OPEN_SEARCH = "hestia:open-search";
export const openSearch = () => window.dispatchEvent(new Event(OPEN_SEARCH));

type Item = {
  key: string;
  group: string;
  icon: LucideIcon;
  title: string;
  detail?: string;
  snippet?: string; // may contain <mark>…</mark> from the API
  external?: boolean;
  run: () => void;
};

const SOURCE = { ntrs: "NTRS", psi: "PSI", nasa_resource: "NASA" } as Record<string, string>;
const OUTCOME = { extinction: "flame went out", complete_burn: "burned completely", disruption: "droplet disrupted" } as Record<string, string>;

/** Renders an API snippet: only <mark> is kept, everything else stays plain text. */
function Highlighted({ text }: { text: string }) {
  return (
    <>
      {text.split(/(<mark>.*?<\/mark>)/g).map((part, i) =>
        part.startsWith("<mark>") ? (
          <mark key={i} className="rounded-sm bg-ember-tint px-0.5 text-ember">{part.slice(6, -7)}</mark>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </>
  );
}

export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [res, setRes] = useState<Schemas["SearchResponse"] | null>(null);
  const [loading, setLoading] = useState(false);
  const [active, setActive] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLDivElement>(null);

  const close = useCallback(() => { setOpen(false); setQ(""); setRes(null); setActive(0); }, []);

  // Ctrl/⌘+K and the top bar's button open it; Escape closes it.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setOpen((o) => !o); }
      else if (e.key === "Escape") close();
    };
    const onOpen = () => setOpen(true);
    window.addEventListener("keydown", onKey);
    window.addEventListener(OPEN_SEARCH, onOpen);
    return () => { window.removeEventListener("keydown", onKey); window.removeEventListener(OPEN_SEARCH, onOpen); };
  }, [close]);

  useEffect(() => { if (open) input.current?.focus(); }, [open]);

  // Debounced search; a newer keystroke cancels the request in flight.
  useEffect(() => {
    const term = q.trim();
    if (term.length < 2) return;
    const ctrl = new AbortController();
    const id = setTimeout(() => {
      setLoading(true);
      api.search(term, ctrl.signal)
        .then((r) => { setRes(r); setActive(0); })
        .catch(() => undefined)
        .finally(() => setLoading(false));
    }, 140);
    return () => { clearTimeout(id); ctrl.abort(); };
  }, [q]);

  const go = useCallback((fn: () => void) => () => { fn(); close(); }, [close]);

  const items = useMemo<Item[]>(() => {
    const term = q.trim();
    if (term.length < 2) return [];
    const out: Item[] = [];
    for (const e of res?.experiments ?? []) {
      out.push({ key: `e-${e.code}`, group: "Experiments", icon: FlaskConical, title: e.code, detail: e.name,
        run: go(() => router.push(`/experiments/${encodeURIComponent(e.code)}`)) });
    }
    for (const t of res?.tests ?? []) {
      const conds = [t.fuel, t.oxygen_percent != null ? `${t.oxygen_percent}% O₂` : null, t.co2_percent ? `${t.co2_percent}% CO₂` : null,
        t.initial_diameter_mm != null ? `d₀ ${t.initial_diameter_mm} mm` : null].filter(Boolean).join(" · ");
      const sim = new URLSearchParams({
        fuel: t.fuel ?? "", o2: String(t.oxygen_percent ?? ""), p: String(t.pressure_kpa ?? ""),
        d0: String(t.initial_diameter_mm ?? ""), co2: String(t.co2_percent ?? 0),
      });
      const runnable = t.experiment_code === "FLEX" && t.fuel && t.oxygen_percent != null && t.initial_diameter_mm != null;
      out.push({ key: `t-${t.run_label}`, group: "Tests", icon: Flame, title: t.run_label,
        detail: `${conds} · ${OUTCOME[t.outcome] ?? t.outcome}${runnable ? " · open in simulator" : ""}`,
        run: go(() => router.push(runnable ? `/simulator?${sim}` : `/experiments/${t.experiment_code}`)) });
    }
    for (const f of res?.findings ?? []) {
      out.push({ key: `f-${f.statement.slice(0, 40)}`, group: "Findings", icon: Lightbulb,
        title: f.statement, detail: [f.experiment_code, f.source_label].filter(Boolean).join(" · "), external: !!f.url,
        run: go(() => (f.url ? window.open(f.url, "_blank", "noopener") : router.push("/relevance"))) });
    }
    for (const d of res?.documents ?? []) {
      out.push({ key: `d-${d.source_type}-${d.external_id}`, group: "NASA sources", icon: FileText, title: d.title,
        detail: `${SOURCE[d.source_type] ?? d.source_type} ${d.external_id}${d.page != null ? ` · p.${d.page}` : ""}`,
        snippet: d.snippet, external: !!d.url,
        run: go(() => d.url && window.open(d.url, "_blank", "noopener")) });
    }
    out.push({ key: "ask", group: "Ask", icon: Sparkles, title: `Ask Hestia: “${term}”`,
      detail: "Cited answer from the NASA corpus",
      run: go(() => router.push(`/assistant?q=${encodeURIComponent(term)}`)) });
    return out;
  }, [res, q, go, router]);

  // Keep the active row in view.
  useEffect(() => {
    list.current?.querySelector(`[data-index="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active]);

  if (!open) return null;

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, items.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
    else if (e.key === "Enter" && items[active]) { e.preventDefault(); items[active].run(); }
  };

  let lastGroup = "";
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-[rgba(4,5,8,0.66)] px-4 pt-[10vh] backdrop-blur-sm" onMouseDown={close}>
      <div
        role="dialog" aria-modal="true" aria-label="Search Hestia"
        className="glass flex max-h-[75vh] w-full max-w-[720px] flex-col overflow-hidden rounded-lg border border-line-strong shadow-2xl"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <label className="flex items-center gap-3 border-b border-line px-5 py-4">
          <Search aria-hidden size={18} strokeWidth={1.75} className="text-fg-3" />
          <span className="sr-only">Search experiments, findings, NASA sources and tests</span>
          <input
            ref={input} value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={onKeyDown}
            role="combobox" aria-expanded={items.length > 0} aria-controls="search-results"
            aria-activedescendant={items[active] ? `search-${active}` : undefined}
            placeholder="Search experiments, findings, NASA sources, tests (FLEX-086, methanol 12%)…"
            className="min-w-0 flex-1 bg-transparent text-[16px] text-fg outline-none placeholder:text-fg-3"
          />
          {loading && <span className="t-mono-s text-fg-3">…</span>}
          <kbd className="t-mono-s rounded-sm border border-line-strong px-1.5 py-0.5 text-fg-3">Esc</kbd>
        </label>

        <div ref={list} id="search-results" role="listbox" className="flex-1 overflow-y-auto p-2">
          {q.trim().length < 2 && (
            <p className="t-body-s px-3 py-6 text-center text-fg-3">
              Type at least two characters. Try <b className="text-fg-2">smoke detector</b>, <b className="text-fg-2">FLEX-086</b> or <b className="text-fg-2">methanol 12%</b>.
            </p>
          )}
          {items.map((it, i) => {
            const header = it.group !== lastGroup ? it.group : null;
            lastGroup = it.group;
            const Icon = it.icon;
            return (
              <div key={it.key}>
                {header && <p className="t-caps-s px-3 pt-3 pb-1.5 text-fg-3">{header}</p>}
                <button
                  id={`search-${i}`} data-index={i} type="button" role="option" aria-selected={i === active}
                  onMouseEnter={() => setActive(i)} onClick={it.run}
                  className={cx("flex w-full items-start gap-3 rounded-md px-3 py-2.5 text-left transition", i === active ? "bg-raised" : "hover:bg-raised")}
                >
                  <Icon aria-hidden size={16} strokeWidth={1.75} className={cx("mt-0.5 shrink-0", it.group === "Ask" ? "text-ember" : "text-fg-3")} />
                  <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                    <span className="line-clamp-2 text-[14px] text-fg">{it.title}</span>
                    {it.detail && <span className="t-mono-s normal-case text-fg-3">{it.detail}</span>}
                    {it.snippet && <span className="t-body-s line-clamp-2 text-fg-2"><Highlighted text={it.snippet} /></span>}
                  </span>
                  {it.external && <ArrowUpRight aria-hidden size={14} className="mt-1 shrink-0 text-fg-3" />}
                </button>
              </div>
            );
          })}
        </div>

        <div className="t-mono-s flex justify-between gap-3 border-t border-line px-5 py-2.5 normal-case text-fg-3">
          <span>↑ ↓ to move · Enter to open</span>
          <span>Ctrl/⌘ K</span>
        </div>
      </div>
    </div>
  );
}
