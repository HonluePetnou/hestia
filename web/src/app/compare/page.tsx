import { Plus, Sparkles, X } from "lucide-react";
import Link from "next/link";
import { Suspense } from "react";

import { ArtStrip } from "@/components/visuals";
import { Badge, Bar, Card, CardHeader, Citation, ErrorBox, Fact, Loading, PageHeader, cx } from "@/components/ui";
import { api, attempt, type Experiment, type Outcome } from "@/lib/api";
import { metaFor, shortPlatform } from "@/lib/content";

const DEFAULT = ["BASS", "FLEX", "SAFFIRE"];
const MIX_COLOR: Record<Outcome, string> = {
  spread: "bg-ember", extinction: "bg-data", complete_burn: "bg-fg-2", disruption: "bg-warn", unknown: "bg-fg-3",
};

const range = (vals: (number | null | undefined)[], unit: string) => {
  const v = vals.filter((x): x is number => x != null);
  if (!v.length) return "—";
  const [lo, hi] = [Math.min(...v), Math.max(...v)];
  return lo === hi ? `${lo}${unit}` : `${lo}–${hi}${unit}`;
};
const avg = (v: number[]) => (v.length ? v.reduce((a, b) => a + b, 0) / v.length : 0);

function summarize(e: Experiment) {
  const runs = e.test_runs ?? [];
  const counts = new Map<Outcome, number>();
  for (const r of runs) counts.set(r.outcome ?? "unknown", (counts.get(r.outcome ?? "unknown") ?? 0) + 1);
  return {
    fuels: [...new Set(runs.map((r) => r.fuel).filter(Boolean))].join(", ") || "—",
    o2: range(runs.map((r) => r.oxygen_percent), "%"),
    pressure: range(runs.map((r) => r.pressure_kpa), " kPa"),
    flow: range(runs.map((r) => r.flow_velocity_cm_s), " cm/s"),
    mix: [...counts.entries()].map(([k, n]) => ({ outcome: k, share: n / Math.max(runs.length, 1) })).sort((a, b) => b.share - a.share),
    moon: avg((e.findings ?? []).map((f) => f.relevance_moon)),
    mars: avg((e.findings ?? []).map((f) => f.relevance_mars)),
  };
}

async function Selection({ codes }: { codes: string[] }) {
  const { data } = await attempt(api.listExperiments());
  const others = (data?.items ?? []).map((e) => e.code).filter((c) => !codes.includes(c));
  const href = (list: string[]) => `/compare?codes=${list.join(",")}`;
  return (
    <div className="flex flex-wrap items-center gap-2.5">
      {codes.map((c) => (
        <Link
          key={c}
          href={href(codes.filter((x) => x !== c))}
          aria-label={`Remove ${c}`}
          className="t-caps flex items-center gap-2.5 rounded-full border border-line-strong bg-raised py-2.5 pr-3 pl-4 hover:border-ember-line"
        >
          {c} <X aria-hidden size={14} className="text-fg-3" />
        </Link>
      ))}
      {codes.length < 3 && others.length > 0 && (
        <details className="relative">
          <summary className="t-caps flex cursor-pointer list-none items-center gap-2 rounded-full border border-dashed border-line-strong py-2.5 pr-4 pl-3.5 text-fg-2 hover:text-fg">
            <Plus aria-hidden size={14} className="text-ember" /> Add
          </summary>
          <div className="glass absolute right-0 z-10 mt-2 flex min-w-40 flex-col rounded-md p-1.5">
            {others.map((c) => (
              <Link key={c} href={href([...codes, c])} className="t-caps rounded-sm px-3 py-2 hover:bg-raised">{c}</Link>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

async function KeyDifferences({ codes }: { codes: string[] }) {
  if (codes.length < 2) return <p className="t-body-s text-fg-3">Add a second experiment to see the key differences.</p>;
  const { data, error } = await attempt(api.compareInsights(codes));
  if (!data) return <ErrorBox error={error} />;
  if (!data.points.length) return <p className="t-body-s text-fg-3">No sourced difference found for this selection.</p>;
  return (
    <>
      {data.points.map((p) => (
        <div key={p.text} className="flex flex-col items-start gap-2">
          <p className="t-body-m">{p.text}</p>
          <div className="flex flex-wrap gap-1.5">
            {(p.citations ?? []).map((c) => (
              <Citation key={`${c.ntrs_id}-${c.page}`} ntrsId={c.ntrs_id} page={c.page} url={c.url} />
            ))}
          </div>
        </div>
      ))}
      <p className="t-caps-s text-fg-3">
        {data.generated_by.startsWith("llm") ? "Generated from NASA sources · citations verified" : "From sourced findings · connect an LLM for a generated summary"}
      </p>
    </>
  );
}

async function Comparison({ codes }: { codes: string[] }) {
  if (!codes.length) return <p className="t-body-m text-fg-2">Pick at least one experiment to compare.</p>;
  const { data, error } = await attempt(api.compare(codes));
  if (!data) return <ErrorBox error={error} />;
  const rows = data.experiments.map((e) => ({ e, s: summarize(e) }));
  const best = [...rows].sort((a, b) => b.s.mars - a.s.mars)[0];

  return (
    <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-[repeat(3,300px)_1fr]">
      {rows.map(({ e, s }) => (
        <Card key={e.code} className="p-5">
          <ArtStrip colors={metaFor(e.code).art} className="h-[72px]" />
          <div className="flex flex-col gap-0.5">
            <Link href={`/experiments/${e.code}`} className="font-display text-[20px] hover:text-ember">{e.code}</Link>
            <span className="t-body-s text-fg-3">{e.name}</span>
          </div>
          <div>
            <Fact top={false} label="Platform" value={shortPlatform(e.platform)} />
            <Fact top={false} label="Fuels" value={s.fuels} />
            <Fact top={false} label="Oxygen" value={s.o2} />
            <Fact top={false} label="Pressure" value={s.pressure} />
            <Fact top={false} label="Flow" value={s.flow} />
            <Fact top={false} label="Test runs" value={e.test_run_count} />
          </div>
          <div className="flex flex-col gap-2">
            <span className="t-caps-s text-fg-3">Outcome mix</span>
            <div className="flex gap-[3px]">
              {s.mix.map((m) => <span key={m.outcome} className={cx("h-1.5 rounded-full", MIX_COLOR[m.outcome])} style={{ flex: m.share }} />)}
            </div>
            <div className="flex flex-wrap gap-x-3 gap-y-1.5">
              {s.mix.map((m) => (
                <span key={m.outcome} className="flex items-center gap-1.5">
                  <span className={cx("size-1.5 rounded-full", MIX_COLOR[m.outcome])} />
                  <span className="t-caps-s text-fg-2">{m.outcome.replace("_", " ")} {Math.round(m.share * 100)}%</span>
                </span>
              ))}
            </div>
          </div>
          <div className="mt-auto flex flex-col gap-3 pt-4">
            {([["Moon relevance", s.moon, "bg-moon", "text-moon"], ["Mars relevance", s.mars, "bg-mars", "text-mars"]] as const).map(([l, v, bg, fg]) => (
              <div key={l} className="flex flex-col gap-1.5">
                <div className="flex justify-between"><span className="t-caps-s text-fg-3">{l}</span><span className={cx("t-mono-m", fg)}>{v.toFixed(2)}</span></div>
                <Bar value={v} color={bg} height={6} />
              </div>
            ))}
          </div>
        </Card>
      ))}

      <Card accent className="p-[22px] lg:col-span-2 xl:col-span-1 bg-[radial-gradient(ellipse_at_50%_100%,rgba(255,122,48,0.16),transparent_60%),var(--color-bg-glass)]">
        <CardHeader title="Key differences" meta="AI · cited" />
        <Sparkles aria-hidden size={22} strokeWidth={1.75} className="text-ember" />
        <Suspense fallback={<p className="t-body-s text-fg-3">Reading the NASA sources…</p>}>
          <KeyDifferences codes={data.experiments.map((e) => e.code)} />
        </Suspense>
        {best && (
          <div className="mt-auto flex flex-col gap-1.5 rounded-md border border-line-strong bg-raised p-3.5">
            <span className="t-caps-s text-fg-3">Most relevant for Mars habitats</span>
            <div className="flex items-center gap-2.5">
              <span className="font-display text-[18px]">{best.e.code}</span>
              <Badge tone="accent">Score {best.s.mars.toFixed(2)}</Badge>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}

async function Body({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const { codes } = await searchParams;
  const list = typeof codes === "string" ? codes.split(",").map((c) => c.trim().toUpperCase()).filter(Boolean).slice(0, 3) : DEFAULT;
  return (
    <>
      <PageHeader
        badge={<Badge tone="accent" className="self-start">Side by side</Badge>}
        title="Compare"
        subtitle="Put up to three investigations next to each other: conditions, outcomes and relevance."
        aside={<Selection codes={list} />}
      />
      <Comparison codes={list} />
    </>
  );
}

export default function Page(props: PageProps<"/compare">) {
  return (
    <div className="flex flex-col gap-6">
      <Suspense fallback={<Loading />}>
        <Body searchParams={props.searchParams} />
      </Suspense>
    </div>
  );
}
