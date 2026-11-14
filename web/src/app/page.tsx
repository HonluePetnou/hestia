import { ArrowUpRight, FileText, Flame, FlaskConical, Send, Sparkles } from "lucide-react";
import Link from "next/link";
import { Suspense, type CSSProperties } from "react";

import { CountUp } from "@/components/CountUp";
import { ArtStrip, DropletFlame, Radar } from "@/components/visuals";
import { Badge, Bar, Card, CardHeader, ErrorBox, IconButton, Loading, Stat, cx } from "@/components/ui";
import { api, attempt, type Schemas } from "@/lib/api";
import { metaFor } from "@/lib/content";

function Hero({ stats }: { stats?: Schemas["StatsResponse"] }) {
  const reports = stats?.documents ? String(stats.documents) : "—";
  const d = (s: number) => ({ "--delay": `${s}s` }) as CSSProperties;
  return (
    <section className="grid items-center gap-8 lg:grid-cols-[640px_1fr_auto] lg:gap-0">
      <div className="flex flex-col gap-7">
        <div className="rise self-start" style={d(0)}><Badge tone="success">Knowledge base · {reports} NASA reports</Badge></div>
        <h1 className="t-display-xl">
          <span className="rise block text-fg" style={d(0.1)}>Guard the<br />flame</span>
          <span className="rise block text-ember" style={d(0.25)}>beyond Earth.</span>
        </h1>
        <p className="rise t-body-l max-w-[520px] text-fg-2" style={d(0.4)}>
          Decades of NASA microgravity combustion experiments, summarized, ranked and explained for Moon and Mars
          fire safety. Every answer cites its NASA source.
        </p>
        <div className="rise flex flex-wrap gap-4" style={d(0.55)}>
          <Link href="/assistant" className="t-caps inline-flex items-center gap-3 rounded-full bg-inverse px-6 py-3 text-fg-inverse transition hover:bg-white/90">
            Ask the assistant <ArrowUpRight aria-hidden size={16} strokeWidth={1.75} />
          </Link>
          <Link href="/experiments" className="t-caps inline-flex items-center gap-3 rounded-full border border-line-strong px-6 py-3 text-fg transition hover:bg-raised">
            Explore experiments <ArrowUpRight aria-hidden size={16} strokeWidth={1.75} />
          </Link>
        </div>
      </div>

      <div className="rise relative mx-auto h-[540px] w-full max-w-[600px]" style={d(0.2)}>
        <DropletFlame className="absolute inset-0 h-full w-full" />
        <div className="rise glass absolute top-[70px] left-[60%] flex flex-col gap-1 rounded-lg px-4 py-3 whitespace-nowrap" style={d(0.9)}>
          <span className="t-caps-s text-fg-3">● Featured test</span>
          <span className="font-display text-[16px] text-fg">FLEX · n-heptane</span>
          <span className="t-mono-s text-fg-2">O₂ 21% · 1 atm · d₀ 3.0 mm</span>
        </div>
      </div>

      <div className="rise flex justify-center gap-7 border-line lg:flex-col lg:border-l lg:pl-6" style={d(0.7)}>
        <Stat icon={FlaskConical} value={stats ? <CountUp value={stats.experiments} pad={2} /> : "—"} label="Experiments indexed" />
        <Stat icon={FileText} value={stats?.documents ? <CountUp value={stats.documents} /> : "—"} label="NASA reports" />
        <Stat icon={Flame} value={stats ? <CountUp value={stats.flex_tests} /> : "—"} label="Droplet tests (FLEX)" />
      </div>
    </section>
  );
}

async function Overview() {
  const { data, error } = await attempt(
    Promise.all([api.stats(), api.listExperiments(), api.ranking("moon"), api.ranking("mars"), api.getExperiment("SAFFIRE")]),
  );
  if (!data) return <><Hero /><ErrorBox error={error} /></>;
  const [stats, experiments, moon, mars, featured] = data;
  const timeline = [...experiments.items]
    .map((e) => ({ code: e.code, desc: metaFor(e.code).tagline, year: (e.years ?? "").match(/\d{4}/)?.[0] ?? "—" }))
    .sort((a, b) => a.year.localeCompare(b.year));
  const latest = timeline.reduce((acc, t) => (t.year > acc ? t.year : acc), "");

  const dots = [
    ...moon.findings.map((f, i) => ({ target: "moon" as const, r: (1 - f.relevance_moon) * 46 + 8, a: i * 2.1 })),
    ...mars.findings.map((f, i) => ({ target: "mars" as const, r: (1 - f.relevance_mars) * 46 + 8, a: i * 2.1 + 1.05 })),
  ].map((d) => ({ x: Math.cos(d.a) * d.r, y: Math.sin(d.a) * d.r * 0.92, target: d.target, size: 6 }));

  return (
    <>
      <Hero stats={stats} />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <Card className="min-h-[291px]">
          <CardHeader title="Knowledge base" meta="NTRS" />
          <div className="flex-1" />
          <div className="flex items-baseline gap-2">
            <span className="t-data-l">{stats.chunks.toLocaleString("en-US")}</span>
            <span className="t-body-s text-fg-3">passages searchable</span>
          </div>
          <Bar value={stats.findings ? Math.min(stats.findings / 25, 1) : 0} />
          <div className="flex items-center justify-between">
            <Badge tone={stats.live_data ? "success" : "warning"}>{stats.live_data ? `${stats.findings} sourced findings` : "Mock data"}</Badge>
            <span className="t-mono-s text-fg-2">{stats.year_min && stats.year_max ? `${stats.year_min}–${stats.year_max}` : "—"}</span>
          </div>
        </Card>

        <Card className="min-h-[291px]">
          <CardHeader title="Featured" meta={featured.platform?.split(" ")[0] ?? ""} />
          <ArtStrip colors={metaFor(featured.code).art} className="h-24" />
          <div className="flex items-center justify-between gap-3">
            <div className="flex flex-col gap-1">
              <span className="font-display text-[18px]">{featured.code}</span>
              <span className="t-body-s text-fg-3">{featured.name}</span>
            </div>
            <IconButton icon={ArrowUpRight} label={`Open ${featured.code}`} href={`/experiments/${featured.code}`} size={36} />
          </div>
        </Card>

        <Card className="min-h-[291px]">
          <CardHeader title="Moon vs Mars" meta="Live" />
          <Radar dots={dots} />
          <div className="mt-auto flex items-center justify-between">
            <div className="flex flex-col gap-1.5">
              <div className="flex items-baseline gap-2">
                <span className="t-data-l">{moon.findings.length}</span>
                <span className="t-body-s text-fg-3">findings ranked</span>
              </div>
              <div className="flex gap-3.5">
                {(["moon", "mars"] as const).map((t) => (
                  <span key={t} className="flex items-center gap-1.5">
                    <span className={cx("size-1.5 rounded-full", t === "moon" ? "bg-moon" : "bg-mars")} />
                    <span className="t-caps-s text-fg-2">{t}</span>
                  </span>
                ))}
              </div>
            </div>
            <IconButton icon={ArrowUpRight} label="Open relevance ranking" href="/relevance" size={36} />
          </div>
        </Card>

        <Card className="min-h-[291px]">
          <CardHeader title="Timeline" meta="ISS era" />
          <ol className="flex flex-col gap-1">
            {timeline.map((t) => (
              <li key={t.code}>
                <Link
                  href={`/experiments/${t.code}`}
                  className={cx(
                    "flex items-center gap-2.5 rounded-md border px-2.5 py-1.5 transition hover:bg-raised",
                    t.year === latest ? "border-line-strong bg-raised" : "border-transparent",
                  )}
                >
                  <span className={cx("size-[7px] rounded-full", t.year === latest ? "bg-ember" : "bg-ok")} />
                  <span className="flex flex-1 flex-col">
                    <span className="text-[13px] font-semibold text-fg">{t.code}</span>
                    <span className="t-caps-s text-fg-3">{t.desc}</span>
                  </span>
                  <span className={cx("t-mono-s", t.year === latest ? "text-ember" : "text-fg-2")}>{t.year}</span>
                </Link>
              </li>
            ))}
          </ol>
        </Card>

        <Card accent className="min-h-[291px] bg-[radial-gradient(ellipse_at_50%_80%,rgba(255,122,48,0.22),transparent_60%),var(--color-bg-glass)]">
          <CardHeader title="Ask Hestia" meta="AI · cited" />
          <Sparkles aria-hidden size={22} strokeWidth={1.75} className="text-ember" />
          <p className="t-body-m">“How does flame spread change at lunar gravity?”</p>
          <form action="/assistant" className="mt-auto flex items-center gap-2 rounded-full border border-line bg-raised py-1.5 pr-1.5 pl-3.5">
            <label htmlFor="overview-q" className="sr-only">Question</label>
            <input id="overview-q" name="q" placeholder="Ask about fire data…" className="t-body-s min-w-0 flex-1 bg-transparent text-fg outline-none placeholder:text-fg-3" />
            <button type="submit" aria-label="Ask" className="flex size-[30px] items-center justify-center rounded-full bg-ember text-fg-inverse">
              <Send aria-hidden size={14} strokeWidth={1.75} />
            </button>
          </form>
        </Card>
      </div>
    </>
  );
}

export default function Page() {
  return (
    <div className="flex flex-col gap-9">
      <Suspense fallback={<><Hero /><Loading /></>}>
        <Overview />
      </Suspense>
    </div>
  );
}
