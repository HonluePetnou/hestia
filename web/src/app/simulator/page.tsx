"use client";

import { ChevronDown, Pause, Play } from "lucide-react";
import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";

import { Gauge } from "@/components/visuals";
import { Badge, Button, Card, CardHeader, ErrorBox, Fact, Loading } from "@/components/ui";
import { api, type Schemas } from "@/lib/api";

// WebGL only exists in the browser, so the canvas is never server-rendered.
const DropletScene = dynamic(() => import("@/components/DropletScene"), {
  ssr: false,
  loading: () => <div className="flex h-full items-center justify-center"><Loading label="Loading 3D scene…" /></div>,
});

// The model is trained on FLEX Table IX, which only contains these two fuels.
const FUELS = ["n-heptane", "methanol"];
const STANDOFF = 5.5; // flame / droplet diameter ratio, typical order of magnitude (approximation)

function Slider({ label, value, unit, min, max, step, onChange }: { label: string; value: number; unit: string; min: number; max: number; step: number; onChange: (v: number) => void }) {
  const fill = ((value - min) / (max - min)) * 100;
  return (
    <label className="flex flex-col gap-2.5">
      <span className="flex items-baseline justify-between">
        <span className="t-caps-s text-fg-3">{label}</span>
        <span className="flex items-baseline gap-1"><span className="font-display text-[18px]">{value}</span><span className="t-mono-s text-fg-3">{unit}</span></span>
      </span>
      <input type="range" className="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} style={{ ["--fill" as string]: `${fill}%` }} />
      <span className="t-mono-s flex justify-between text-fg-3"><span>{min}</span><span>{max}</span></span>
    </label>
  );
}

export default function Page() {
  const [fuel, setFuel] = useState("n-heptane");
  const [o2, setO2] = useState(21);
  const [pressure, setPressure] = useState(101);
  const [d0, setD0] = useState(3.0);
  const [co2, setCo2] = useState(0);
  const [info, setInfo] = useState<Schemas["ModelInfo"] | null>(null);
  const [pred, setPred] = useState<Schemas["PredictResponse"] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const raf = useRef<number | null>(null);

  const run = useCallback(async () => {
    setPending(true); setError(null); setPlaying(false); setT(0);
    try {
      setPred(await api.predict({ fuel, oxygen_percent: o2, pressure_kpa: pressure, initial_diameter_mm: d0, co2_percent: co2 }));
    } catch (e) { setError(e); } finally { setPending(false); }
  }, [fuel, o2, pressure, d0, co2]);

  useEffect(() => {
    api.modelInfo().then(setInfo, () => undefined);
  }, []);

  // Predict automatically (debounced) whenever a condition changes.
  useEffect(() => {
    let alive = true;
    const id = setTimeout(() => {
      api.predict({ fuel, oxygen_percent: o2, pressure_kpa: pressure, initial_diameter_mm: d0, co2_percent: co2 })
        .then((p) => { if (alive) { setPred(p); setError(null); setT(0); } })
        .catch((e: unknown) => { if (alive) setError(e); });
    }, 250);
    return () => { alive = false; clearTimeout(id); };
  }, [fuel, o2, pressure, d0, co2]);

  const K = pred?.burn_rate_k ?? 0.6;
  const burnTime = (d0 * d0) / Math.max(K, 0.01); // d² law: d² = d0² − K·t
  const d = Math.sqrt(Math.max(d0 * d0 - K * t, 0));

  useEffect(() => {
    if (!playing) return;
    let last = performance.now();
    const tick = (now: number) => {
      const dt = ((now - last) / 1000) * (burnTime / 6); // play the whole burn in ~6 s
      last = now;
      setT((prev) => {
        const next = prev + dt;
        if (next >= burnTime) { setPlaying(false); return burnTime; }
        return next;
      });
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => { if (raf.current) cancelAnimationFrame(raf.current); };
  }, [playing, burnTime]);

  const scale = 0.18; // scene units per mm
  const progress = burnTime ? t / burnTime : 0;

  return (
    <div className="grid flex-1 gap-4 xl:grid-cols-[330px_1fr_320px]">
      {/* Conditions */}
      <Card className="gap-[18px] p-[22px]">
        <CardHeader title="Conditions" meta="FLEX range" />
        <label className="flex flex-col gap-2.5">
          <span className="t-caps-s text-fg-3">Fuel</span>
          <span className="relative flex items-center">
            <select value={fuel} onChange={(e) => setFuel(e.target.value)} className="w-full appearance-none rounded-md border border-line bg-raised px-3.5 py-2.5 text-[15px] font-medium text-fg outline-none focus-visible:border-ember">
              {FUELS.map((f) => <option key={f}>{f}</option>)}
            </select>
            <ChevronDown aria-hidden size={16} className="pointer-events-none absolute right-3 text-fg-2" />
          </span>
        </label>
        <Slider label="Oxygen" value={o2} unit="% O₂" min={10} max={40} step={1} onChange={setO2} />
        <Slider label="Pressure" value={pressure} unit="kPa" min={50} max={320} step={1} onChange={setPressure} />
        <Slider label="Initial diameter" value={d0} unit="mm" min={1} max={5} step={0.1} onChange={setD0} />
        <Slider label="CO₂ suppressant" value={co2} unit="% CO₂" min={0} max={70} step={1} onChange={setCo2} />
        <div className="mt-auto flex flex-col gap-2 pt-2">
          <Button variant="accent" className="w-full" onClick={() => void run()} disabled={pending}>
            {pending ? "Predicting…" : "Replay from t = 0"}
          </Button>
          <p className="t-caps-s text-center text-fg-3">
            {info?.trained
              ? `Trained on ${info.k_samples} ISS tests · R² ${info.k_r2_cv?.toFixed(2)} · AUC ${info.extinction_auc_cv?.toFixed(2)}`
              : `Model · ${pred?.model ?? "—"}`}
          </p>
          <p className="t-caps-s text-center text-fg-3">Microgravity only · FLEX, NASA/TP-2015-216046</p>
        </div>
      </Card>

      {/* Viewport */}
      <section className="glass relative min-h-[560px] overflow-hidden rounded-lg">
        <div aria-hidden className="absolute inset-0 bg-[linear-gradient(rgba(230,232,238,0.04)_1px,transparent_1px),linear-gradient(90deg,rgba(230,232,238,0.04)_1px,transparent_1px)] bg-size-[12.5%_12.5%]" />
        <div className="absolute inset-0">
          <DropletScene droplet={Math.max(d * scale * 0.5, 0.004)} flame={Math.max(d * STANDOFF * scale * 0.5, 0.02)} />
        </div>
        <div className="pointer-events-none absolute top-5 right-5 left-5 flex items-center justify-between">
          <div className="flex items-center gap-2.5"><span className="t-caps">3D droplet flame</span><Badge tone="success">Live</Badge></div>
          <span className="t-caps-s text-fg-3">Drag to orbit · scroll to zoom</span>
        </div>
        <div className="glass absolute right-6 bottom-6 left-6 flex items-center gap-3.5 rounded-full py-2 pr-[18px] pl-2">
          <button
            type="button"
            aria-label={playing ? "Pause" : "Play burn"}
            onClick={() => { if (t >= burnTime) setT(0); setPlaying((p) => !p); }}
            className="glass flex size-10 items-center justify-center rounded-full text-fg"
          >
            {playing ? <Pause aria-hidden size={16} /> : <Play aria-hidden size={16} />}
          </button>
          <input
            type="range" aria-label="Time" className="range flex-1" min={0} max={burnTime} step={burnTime / 200} value={t}
            onChange={(e) => { setPlaying(false); setT(Number(e.target.value)); }}
            style={{ ["--fill" as string]: `${progress * 100}%` }}
          />
          <span className="t-mono-s whitespace-nowrap normal-case text-fg">t = {t.toFixed(2)} s / {burnTime.toFixed(2)} s</span>
        </div>
      </section>

      {/* Readouts */}
      <Card className="gap-[18px] p-[22px]">
        <CardHeader title="Prediction" meta={pred?.model ?? ""} />
        {error !== null && <ErrorBox error={error} />}
        {pred && !pred.in_training_range && (
          <Badge tone="warning" className="self-start">Outside the tested range · extrapolation</Badge>
        )}
        <Gauge value={K / 1.2} display={K.toFixed(2)} unit="mm²/s" label="Burn rate K" color="var(--color-accent-default)" />
        <Gauge value={pred?.extinction_probability ?? 0} display={`${Math.round((pred?.extinction_probability ?? 0) * 100)}%`} unit="chance" label="Extinction probability" color="var(--color-data-primary)" />
        <div>
          <Fact label="Droplet diameter" value={`${d.toFixed(2)} mm`} />
          <Fact label="Flame diameter ≈" value={`${(d * STANDOFF).toFixed(1)} mm`} />
          <Fact label="Burn time (d² law)" value={`${burnTime.toFixed(1)} s`} />
          <Fact label="Atmosphere" value={`${o2}% O₂ · ${co2}% CO₂ · ${pressure} kPa`} />
        </div>
        <div className="mt-auto flex items-center justify-between rounded-md border border-line-strong bg-raised px-3.5 py-3">
          <span className="t-caps-s text-fg-3">Predicted outcome</span>
          {(pred?.extinction_probability ?? 0) >= 0.5
            ? <Badge tone="data">Extinction likely</Badge>
            : <Badge tone="accent">Complete burn</Badge>}
        </div>
      </Card>
    </div>
  );
}
