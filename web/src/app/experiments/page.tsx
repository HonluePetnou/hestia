import Link from "next/link";
import { Suspense } from "react";

import { ErrorBox, Json, Loading, PageHeader, Section } from "@/components/ui";
import { api, attempt } from "@/lib/api";

async function ExperimentList() {
  const { data, error } = await attempt(api.listExperiments());
  if (!data) return <ErrorBox error={error} />;
  return (
    <>
      <Section title={`${data.total} experiments`}>
        <ul className="list-disc pl-5">
          {data.items.map((e) => (
            <li key={e.code}>
              <Link href={`/experiments/${e.code}`} className="underline">
                {e.code}
              </Link>{" "}
              — {e.name} ({e.platform})
            </li>
          ))}
        </ul>
      </Section>
      <Section title="Raw response">
        <Json data={data} />
      </Section>
    </>
  );
}

export default function Page() {
  return (
    <>
      <PageHeader title="Experiment Explorer" subtitle="Filters come in Phase 2." />
      <Suspense fallback={<Loading />}>
        <ExperimentList />
      </Suspense>
    </>
  );
}
