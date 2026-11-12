import { Suspense } from "react";

import { ErrorBox, Json, Loading, PageHeader } from "@/components/ui";
import { api, attempt } from "@/lib/api";

const DEFAULT_CODES = ["BASS", "SAFFIRE", "FLEX"];

async function Comparison({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { codes } = await searchParams;
  const wanted = typeof codes === "string" && codes ? codes.split(",") : DEFAULT_CODES;
  const { data, error } = await attempt(api.compare(wanted));
  return data ? <Json data={data} /> : <ErrorBox error={error} />;
}

export default function Page(props: PageProps<"/compare">) {
  return (
    <>
      <PageHeader title="Compare" subtitle="Try /compare?codes=BASS,FLEX" />
      <Suspense fallback={<Loading />}>
        <Comparison searchParams={props.searchParams} />
      </Suspense>
    </>
  );
}
