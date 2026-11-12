import { Suspense } from "react";

import { TestRunChart } from "@/components/TestRunChart";
import { ErrorBox, Json, Loading, PageHeader, Section } from "@/components/ui";
import { api, attempt } from "@/lib/api";

async function Overview() {
  const { data, error } = await attempt(Promise.all([api.health(), api.listExperiments()]));
  if (!data) return <ErrorBox error={error} />;
  const [health, experiments] = data;
  return (
    <>
      <Section title="API health">
        <Json data={health} />
      </Section>
      <Section title="Test runs per experiment">
        <TestRunChart
          data={experiments.items.map((e) => ({ code: e.code, runs: e.test_run_count ?? 0 }))}
        />
      </Section>
      <Section title={`Experiments (${experiments.total})`}>
        <Json data={experiments.items} />
      </Section>
    </>
  );
}

export default function Page() {
  return (
    <>
      <PageHeader title="Overview" subtitle="Guarding the flame beyond Earth." />
      <Suspense fallback={<Loading />}>
        <Overview />
      </Suspense>
    </>
  );
}
