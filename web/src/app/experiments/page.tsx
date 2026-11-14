import { ArrowUpRight, Plus } from "lucide-react";
import { Suspense } from "react";

import { FilterBar, SearchBox } from "@/components/FilterBar";
import { ArtStrip } from "@/components/visuals";
import { Badge, ErrorBox, IconButton, Loading, PageHeader } from "@/components/ui";
import { api, attempt, type ExperimentFilters, type Gravity, type Outcome } from "@/lib/api";
import { metaFor, shortPlatform } from "@/lib/content";

type SP = Record<string, string | string[] | undefined>;
const one = (v: string | string[] | undefined) => (typeof v === "string" && v ? v : undefined);

async function Grid({ searchParams }: { searchParams: Promise<SP> }) {
  const sp = await searchParams;
  const filters: ExperimentFilters = {
    fuel: one(sp.fuel),
    gravity: one(sp.gravity) as Gravity | undefined,
    outcome: one(sp.outcome) as Outcome | undefined,
    o2_min: one(sp.o2_min) ? Number(sp.o2_min) : undefined,
    o2_max: one(sp.o2_max) ? Number(sp.o2_max) : undefined,
  };
  const { data, error } = await attempt(api.listExperiments(filters));
  if (!data) return <ErrorBox error={error} />;
  const q = one(sp.q)?.toLowerCase();
  const items = q
    ? data.items.filter((e) => `${e.code} ${e.name} ${e.fuels ?? metaFor(e.code).fuels}`.toLowerCase().includes(q))
    : data.items;

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {items.map((e) => {
        const meta = metaFor(e.code);
        return (
          <article key={e.code} className="glass flex flex-col gap-3.5 rounded-lg p-[18px]">
            <ArtStrip colors={meta.art} />
            <div className="flex items-center justify-between gap-3">
              <div className="flex min-w-0 flex-col gap-0.5">
                <h2 className="font-display text-[20px] leading-tight">{e.code}</h2>
                <p className="t-body-s truncate text-fg-3">{e.name}</p>
              </div>
              <IconButton icon={ArrowUpRight} label={`Open ${e.code}`} href={`/experiments/${e.code}`} size={36} />
            </div>
            <div className="flex flex-wrap gap-2">
              {e.platform && <Badge>{shortPlatform(e.platform)}</Badge>}
              <Badge tone="data">Microgravity</Badge>
            </div>
            <dl className="mt-auto grid grid-cols-[84px_1fr_84px] border-t border-line pt-3">
              <div className="flex flex-col gap-1"><dt className="t-caps-s text-fg-3">Test runs</dt><dd className="font-display text-[18px]">{e.test_run_count}</dd></div>
              <div className="flex flex-col gap-1"><dt className="t-caps-s text-fg-3">Fuels</dt><dd className="t-mono-m truncate" title={e.fuels ?? meta.fuels}>{e.fuels ?? meta.fuels}</dd></div>
              <div className="flex flex-col gap-1"><dt className="t-caps-s text-fg-3">Since</dt><dd className="font-display text-[18px]">{e.years?.match(/\d{4}/)?.[0] ?? meta.years}</dd></div>
            </dl>
          </article>
        );
      })}
      {items.length === 0 && (
        <p className="t-body-m col-span-full rounded-lg border border-line p-8 text-center text-fg-2">
          No experiment has a test run matching these filters.
        </p>
      )}
      <a
        href="https://psi.nasa.gov"
        target="_blank"
        rel="noreferrer"
        className="flex min-h-[300px] flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-line-strong p-6 text-center transition hover:border-ember-line"
      >
        <span className="flex size-12 items-center justify-center rounded-full border border-line-strong">
          <Plus aria-hidden size={20} strokeWidth={1.75} className="text-ember" />
        </span>
        <span className="t-h3">Add a PSI dataset</span>
        <span className="t-body-s text-fg-3">Import test matrices from psi.nasa.gov<br />(metadata JSON + tables, no raw video)</span>
      </a>
    </div>
  );
}

export default function Page(props: PageProps<"/experiments">) {
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        badge={<Badge tone="data" className="self-start">PSI · NTRS · 5 investigations</Badge>}
        title="Experiment Explorer"
        subtitle="Filter decades of NASA microgravity combustion tests by fuel, gravity, oxygen and outcome."
        aside={<Suspense><SearchBox /></Suspense>}
      />
      <Suspense><FilterBar /></Suspense>
      <Suspense fallback={<Loading />}>
        <Grid searchParams={props.searchParams} />
      </Suspense>
    </div>
  );
}
