import Link from "next/link";
import { Suspense } from "react";

import { BurnRateChart } from "@/components/BurnRateChart";
import { Badge, Bar, Button, Card, CardHeader, Citation, ErrorBox, Loading, type Tone } from "@/components/ui";
import { api, attempt, type Outcome } from "@/lib/api";
import { metaFor, shortPlatform } from "@/lib/content";

const OUTCOME_TONE: Record<Outcome, Tone> = {
  spread: "accent", extinction: "data", disruption: "warning", complete_burn: "accent", unknown: "neutral",
};
const outcomeLabel = (o: Outcome) => o.replace("_", " ");
const fmt = (v: number | null | undefined, digits = 2) => (v == null ? "—" : v.toFixed(digits));

async function Detail({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  const { data: e, error } = await attempt(api.getExperiment(code));
  if (!e) return <ErrorBox error={error} />;
  const meta = metaFor(e.code);
  const objectives = (e.objectives ?? "").split(/\n|(?<=\.)\s+/).map((s) => s.trim()).filter(Boolean);
  const points = (e.test_runs ?? [])
    .filter((r) => r.oxygen_percent != null && r.burn_rate_k != null)
    .map((r) => ({ o2: r.oxygen_percent!, k: r.burn_rate_k!, outcome: r.outcome ?? "unknown", label: r.run_label ?? "" }));

  return (
    <div className="flex flex-col gap-[22px]">
      <div className="flex flex-wrap items-end justify-between gap-6">
        <div className="flex flex-col gap-2.5">
          <nav aria-label="Breadcrumb" className="t-body-s flex gap-2 text-fg-3">
            <Link href="/experiments" className="hover:text-fg">Experiments</Link><span>/</span><span className="text-fg">{e.code}</span>
          </nav>
          <div className="flex flex-wrap items-baseline gap-5">
            <h1 className="t-display-l">{e.code}</h1>
            <p className="t-h2 text-fg-2">{e.name}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {e.platform && <Badge>{shortPlatform(e.platform)}</Badge>}
            <Badge tone="accent">{meta.tagline}</Badge>
            <Badge tone="data">Microgravity</Badge>
            {e.psi_doi && <Badge>DOI {e.psi_doi}</Badge>}
          </div>
        </div>
        <div className="flex gap-3">
          <Button variant="secondary" icon={false} href={`/compare?codes=${[e.code, ...["FLEX", "SAFFIRE"].filter((c) => c !== e.code)].join(",")}`}>Compare</Button>
          <Button variant="accent" href={`/assistant?q=${encodeURIComponent(`What did ${e.code} show about fire safety?`)}`}>Ask about {e.code}</Button>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[500px_1fr]">
        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader title="About" meta="PSI" />
            <p className="t-body-m text-fg-2">{e.description}</p>
            {objectives.length > 0 && (
              <ul className="flex flex-col gap-2">
                {objectives.map((o) => (
                  <li key={o} className="t-body-s flex items-center gap-2.5"><span className="size-[5px] shrink-0 rounded-full bg-ember" />{o}</li>
                ))}
              </ul>
            )}
          </Card>
          <Card className="flex-1">
            <CardHeader title="Key findings" meta={`${(e.findings ?? []).length} cited`} />
            {(e.findings ?? []).length === 0 && <p className="t-body-s text-fg-3">No finding extracted yet for this experiment.</p>}
            {(e.findings ?? []).map((f) => (
              <div key={f.id} className="flex flex-col gap-2 border-t border-line pt-3">
                <p className="t-body-s">{f.statement}</p>
                <div className="flex flex-wrap items-center gap-3">
                  {(f.sources ?? []).map((s) => <Citation key={`${s.ntrs_id}-${s.page}`} ntrsId={s.ntrs_id} page={s.page} url={s.url} />)}
                  {([["Moon", f.relevance_moon, "bg-moon"], ["Mars", f.relevance_mars, "bg-mars"]] as const).map(([l, v, c]) => (
                    <span key={l} className="flex items-center gap-1.5">
                      <span className="t-caps-s text-fg-3">{l}</span>
                      <Bar value={v} color={c} className="w-11!" />
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </Card>
        </div>

        <div className="flex min-w-0 flex-col gap-4">
          <Card>
            <CardHeader title="Burning rate K vs oxygen" meta={`${points.length} runs`} />
            <div className="flex gap-4">
              <span className="flex items-center gap-1.5"><span className="size-2 rounded-full bg-ember" /><span className="t-caps-s text-fg-2">Complete burn</span></span>
              <span className="flex items-center gap-1.5"><span className="size-2 rounded-full border-[1.5px] border-data" /><span className="t-caps-s text-fg-2">Extinction</span></span>
            </div>
            <BurnRateChart points={points} />
          </Card>
          <Card className="flex-1">
            <CardHeader title="Test runs" meta={`${e.test_run_count} runs`} />
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] border-separate border-spacing-y-1 text-left">
                <thead>
                  <tr className="t-caps-s text-fg-3">
                    {["Run", "Fuel", "O₂", "P (kPa)", "d₀ (mm)", "Outcome", "K (mm²/s)"].map((h) => <th key={h} className="px-2.5 py-1 font-medium">{h}</th>)}
                  </tr>
                </thead>
                <tbody className="t-mono-m">
                  {(e.test_runs ?? []).map((r, i) => (
                    <tr key={`${r.run_label}-${i}`} className={i === 0 ? "bg-raised" : undefined}>
                      <td className="rounded-l-sm px-2.5 py-2 text-fg-2">{r.run_label ?? "—"}</td>
                      <td className="px-2.5 py-2">{r.fuel ?? "—"}</td>
                      <td className="px-2.5 py-2">{r.oxygen_percent != null ? `${r.oxygen_percent}%` : "—"}</td>
                      <td className="px-2.5 py-2">{fmt(r.pressure_kpa, 1)}</td>
                      <td className="px-2.5 py-2">{fmt(r.initial_diameter_mm)}</td>
                      <td className="px-2.5 py-2"><Badge tone={OUTCOME_TONE[r.outcome ?? "unknown"]}>{outcomeLabel(r.outcome ?? "unknown")}</Badge></td>
                      <td className="rounded-r-sm px-2.5 py-2">{fmt(r.burn_rate_k)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

export default function Page(props: PageProps<"/experiments/[code]">) {
  return (
    <Suspense fallback={<Loading />}>
      <Detail params={props.params} />
    </Suspense>
  );
}
