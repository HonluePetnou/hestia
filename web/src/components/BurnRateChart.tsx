"use client";

import { CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from "recharts";

type Point = { o2: number; k: number; outcome: string; label: string };

// SVG presentation attributes don't resolve CSS var(), so chart colors are literal token values.
const C = { ember: "#FF7A30", data: "#5AA9FF", muted: "#858B9B", grid: "#242833", raised: "#181B24", strong: "#3A3F4D" };
const tick = { fill: C.muted, fontSize: 11, fontFamily: "var(--font-jetbrains)" };

/** Burning-rate constant K vs oxygen, colored by outcome (Figma: "Burning rate K vs oxygen"). */
export function BurnRateChart({ points }: { points: Point[] }) {
  const burn = points.filter((p) => p.outcome !== "extinction");
  const ext = points.filter((p) => p.outcome === "extinction");
  if (points.length === 0) {
    return <p className="t-body-s py-16 text-center text-fg-3">No test run with a measured burning rate yet.</p>;
  }
  return (
    <div className="h-[210px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 6, right: 10, bottom: 0, left: -18 }}>
          <CartesianGrid vertical={false} stroke={C.grid} />
          <XAxis type="number" dataKey="o2" unit="%" domain={[15, 40]} tick={tick} tickLine={false} axisLine={false} />
          <YAxis type="number" dataKey="k" domain={[0.4, 1]} tick={tick} tickLine={false} axisLine={false} tickFormatter={(v: number) => v.toFixed(2)} />
          <ZAxis range={[80, 80]} />
          <Tooltip
            cursor={{ stroke: C.strong }}
            contentStyle={{ background: C.raised, border: `1px solid ${C.strong}`, borderRadius: 8, fontSize: 12 }}
            itemStyle={{ color: "#E6E8EE" }}
            formatter={(v, name) => [String(v), name === "o2" ? "O₂ %" : "K (mm²/s)"]}
          />
          <Scatter name="Complete burn" data={burn} fill={C.ember} />
          <Scatter name="Extinction" data={ext} fill="none" stroke={C.data} strokeWidth={1.5} />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
