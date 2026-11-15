import { ArrowUpRight } from "lucide-react";
import Link from "next/link";
import { Suspense } from "react";

import { Planet } from "@/components/visuals";
import { Badge, Bar, Card, CardHeader, Citation, ErrorBox, Fact, IconButton, Loading, PageHeader, cx } from "@/components/ui";
import { api, attempt } from "@/lib/api";
import { TARGETS } from "@/lib/content";

type Target = "moon" | "mars";

function Toggle({ target }: { target: Target }) {
  return (
    <nav aria-label="Target" className="glass flex gap-1 rounded-full p-[5px]">
      {(Object.keys(TARGETS) as Target[]).map((t) => {
        const on = t === target;
        return (
          <Link
            key={t}
            href={`/relevance?target=${t}`}
            aria-current={on ? "page" : undefined}
            className={cx("flex items-center gap-2.5 rounded-full border py-2.5 pr-[18px] pl-4", on ? "border-line-strong bg-raised" : "border-transparent hover:bg-raised/50")}
          >
            <span className={cx("size-2.5 rounded-full", t === "moon" ? "bg-moon" : "bg-mars")} />
            <span className={cx("text-[15px] font-medium", on ? "text-fg" : "text-fg-2")}>{TARGETS[t].label}</span>
            <span className="t-mono-s text-fg-3">{TARGETS[t].gravity}</span>
          </Link>
        );
      })}
    </nav>
  );
}

async function Ranking({ target }: { target: Target }) {
  const { data, error } = await attempt(api.ranking(target));
  if (!data) return <ErrorBox error={error} />;
  return (
    <ol className="flex flex-col gap-2.5">
      {data.findings.map((f, i) => {
        const rel = target === "moon" ? f.relevance_moon : f.relevance_mars;
        return (
          <li key={f.id} className={cx("glass flex items-center gap-5 rounded-lg px-5 py-4", i === 0 && "border-ember-line!")}>
            <span className={cx("t-data-l w-12 shrink-0", i === 0 ? "text-ember" : "text-fg-3")}>{String(i + 1).padStart(2, "0")}</span>
            <div className="flex min-w-0 flex-1 flex-col gap-2">
              <div className="flex flex-wrap items-center gap-2.5">
                {f.experiment_code && <Badge>{f.experiment_code}</Badge>}
                {(f.sources ?? []).map((s) => <Citation key={`${s.ntrs_id}-${s.page}`} ntrsId={s.ntrs_id} page={s.page} url={s.url} />)}
              </div>
              <p className="t-body-m">{f.statement}</p>
            </div>
            <div className="flex w-44 shrink-0 flex-col gap-1.5">
              <div className="flex justify-between">
                <span className="t-caps-s text-fg-3">Score</span>
                <span className={cx("t-mono-m", i === 0 ? "text-ember" : "text-fg")}>{f.score.toFixed(2)}</span>
              </div>
              <Bar value={f.score} color={target === "moon" ? "bg-moon" : "bg-mars"} height={5} />
              <span className="t-caps-s text-fg-3">Rel {rel.toFixed(2)} · Conf {f.confidence.toFixed(2)}</span>
            </div>
            {f.experiment_code && (
              <IconButton icon={ArrowUpRight} label={`Open ${f.experiment_code}`} href={`/experiments/${f.experiment_code}`} size={36} />
            )}
          </li>
        );
      })}
      {data.findings.length === 0 && <p className="t-body-m text-fg-2">No finding ranked yet.</p>}
    </ol>
  );
}

async function Body({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const sp = await searchParams;
  const target: Target = sp.target === "mars" ? "mars" : "moon";
  const t = TARGETS[target];
  return (
    <>
      <PageHeader
        badge={<Badge tone="accent" className="self-start">Ranked by relevance × confidence</Badge>}
        title="Moon & Mars"
        subtitle="Which microgravity findings matter most for fire safety on the next destination."
        aside={<Toggle target={target} />}
      />
      <div className="grid items-start gap-4 xl:grid-cols-[440px_1fr]">
        {/* Auto height, and it stays in view while the findings list scrolls */}
        <Card className="gap-[18px] p-[22px] xl:sticky xl:top-[120px]">
          <CardHeader title={`Target · ${t.label}`} meta={t.program} />
          <Planet target={target} />
          <div>
            {t.facts.map(([l, v]) => <Fact key={l} label={l} value={v} />)}
          </div>
          <p className="t-body-s rounded-md border border-ember-line bg-ember-tint px-3.5 py-3 text-ember-soft">{t.note}</p>
        </Card>
        <div className="flex flex-col gap-2.5">
          <div className="flex justify-between px-1">
            <h2 className="t-caps">Top findings for the {t.label}</h2>
            <span className="t-mono-s text-fg-3">Sort · score ↓</span>
          </div>
          <Ranking target={target} />
        </div>
      </div>
    </>
  );
}

export default function Page(props: PageProps<"/relevance">) {
  return (
    <div className="flex flex-col gap-6">
      <Suspense fallback={<Loading />}>
        <Body searchParams={props.searchParams} />
      </Suspense>
    </div>
  );
}
