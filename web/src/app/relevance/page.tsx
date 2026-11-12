import { Suspense } from "react";

import { ErrorBox, Json, Loading, PageHeader, Section } from "@/components/ui";
import { api, attempt } from "@/lib/api";

async function Ranking({ target }: { target: "moon" | "mars" }) {
  const { data, error } = await attempt(api.ranking(target));
  return data ? <Json data={data} /> : <ErrorBox error={error} />;
}

export default function Page() {
  return (
    <>
      <PageHeader title="Moon & Mars Relevance" subtitle="Findings ranked by relevance." />
      <div className="grid gap-6 lg:grid-cols-2">
        {(["moon", "mars"] as const).map((target) => (
          <Section key={target} title={target === "moon" ? "Moon" : "Mars"}>
            <Suspense fallback={<Loading />}>
              <Ranking target={target} />
            </Suspense>
          </Section>
        ))}
      </div>
    </>
  );
}
