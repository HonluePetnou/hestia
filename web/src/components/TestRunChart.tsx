"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

/** Placeholder chart proving Recharts works. Styling comes later from Figma. */
export function TestRunChart({ data }: { data: { code: string; runs: number }[] }) {
  return (
    <div className="h-64 w-full max-w-xl">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="code" />
          <YAxis allowDecimals={false} />
          <Tooltip />
          <Bar dataKey="runs" fill="currentColor" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
