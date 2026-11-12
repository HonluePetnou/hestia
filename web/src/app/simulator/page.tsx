"use client";

import dynamic from "next/dynamic";

import { Loading, PageHeader } from "@/components/ui";

// WebGL only exists in the browser, so the canvas is never server-rendered.
const DropletScene = dynamic(() => import("@/components/DropletScene"), {
  ssr: false,
  loading: () => <Loading />,
});

export default function Page() {
  return (
    <>
      <PageHeader
        title="3D Droplet Flame Simulator"
        subtitle="Phase 1: a sphere with orbit controls. Flame logic comes later."
      />
      <div className="h-[480px] w-full max-w-3xl rounded border border-gray-200">
        <DropletScene />
      </div>
    </>
  );
}
