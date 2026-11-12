import { Suspense } from "react";

import { ErrorBox, Json, Loading, PageHeader } from "@/components/ui";
import { api, attempt } from "@/lib/api";

async function ExperimentDetail({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  const { data, error } = await attempt(api.getExperiment(code));
  if (!data) return <ErrorBox error={error} />;
  return (
    <>
      <PageHeader title={`${data.code} — ${data.name}`} subtitle={data.platform ?? ""} />
      <Json data={data} />
    </>
  );
}

export default function Page(props: PageProps<"/experiments/[code]">) {
  return (
    <Suspense fallback={<Loading />}>
      <ExperimentDetail params={props.params} />
    </Suspense>
  );
}
