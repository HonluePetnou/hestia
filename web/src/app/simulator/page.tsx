"use client";

import { ArrowUpRight, ChevronDown, Pause, Play } from "lucide-react";
import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";

import { Gauge } from "@/components/visuals";
import type { Gravity } from "@/components/DropletScene";
import { Badge, Button, Card, CardHeader, ErrorBox, Fact, Loading, cx } from "@/components/ui";
import { api, type Schemas } from "@/lib/api";

// WebGL only exists in the browser, so the canvas is never server-rendered.
const DropletScene = dynamic(() => import("@/components/DropletScene"), {
  ssr: false,
  loading: () => <div className="flex h-full items-center justify-center"><Loading label="Loading 3D scene…" /></div>,
});

// The model is trained on FLEX Table IX, which only contains these two fuels.
const FUELS = ["n-heptane", "methanol"];
const STANDOFF = 5.5; // flame / droplet diameter ratio, typical order of magnitude (approximation)
// Median extinction diameter / initial diameter over the 159 FLEX Table IX tests that ended in
// extinction (methanol 0.57, IQR 0.47-0.82; n-heptane 0.84, IQR 0.76-0.96).
const EXT_RATIO: Record<string, number> = { methanol: 0.57, "n-heptane": 0.84 };
const IGNITE = 0.06; // share of the timeline spent igniting
const FADE = 0.15; // extra time after extinction to show the flame going out

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

const OUTCOME: Record<string, { label: string; tone: "data" | "accent" | "warning" }> = {
  extinction: { label: "Flame went out", tone: "data" },
  complete_burn: { label: "Burned completely", tone: "accent" },
  disruption: { label: "Droplet disrupted", tone: "warning" },
};

/* The real ISS test closest to the chosen conditions, with what actually happened. */
function NearestTestCard({ test }: { test: Schemas["NearestTest"] }) {
  const o = OUTCOME[test.outcome] ?? { label: test.outcome, tone: "warning" as const };
  const close = test.distance < 0.5;
  return (
    <div className="flex flex-col gap-2.5 rounded-md border border-ember-line bg-ember-tint px-3.5 py-3">
      <div className="flex items-center justify-between gap-2">
        <span className="t-caps-s text-fg-2">{close ? "Matching NASA test" : "Closest NASA test"}</span>
        <Badge tone={o.tone}>{o.label}</Badge>
      </div>
      <p className="t-mono-s normal-case text-fg">
        {test.test_id} · {test.fuel} · {test.oxygen_percent}% O₂{test.co2_percent ? ` · ${test.co2_percent}% CO₂` : ""}
        {test.he_percent ? ` · ${test.he_percent}% He` : ""} · {test.pressure_kpa} kPa · d₀ {test.initial_diameter_mm} mm
      </p>
      <p className="t-body-s text-fg-2">
        On the ISS: {test.burn_rate_k != null ? `K = ${test.burn_rate_k} mm²/s` : "K not reported"}
        {test.extinction_diameter_mm != null ? `, flame out at d = ${test.extinction_diameter_mm} mm` : ""}.
      </p>
      <a href={test.url} target="_blank" rel="noreferrer" className="t-caps-s inline-flex items-center gap-1.5 text-ember hover:text-ember-soft">
        FLEX report{test.source_page ? `, p.${test.source_page}` : ""} <ArrowUpRight aria-hidden size={12} />
      </a>
    </div>
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
  const [gravity, setGravity] = useState<Gravity>("micro");
  const [labels, setLabels] = useState(true);
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
        .then((p) => {
          if (!alive) return;
          setPred(p); setError(null); setT(0);
          // Replay the burn after each new prediction, unless the user prefers reduced motion.
          setPlaying(!window.matchMedia("(prefers-reduced-motion: reduce)").matches);
        })
        .catch((e: unknown) => { if (alive) setError(e); });
    }, 250);
    return () => { alive = false; clearTimeout(id); };
  }, [fuel, o2, pressure, d0, co2]);

  const K = Math.max(pred?.burn_rate_k ?? 0.6, 0.01);
  const extinguishes = (pred?.extinction_probability ?? 0) >= 0.5;
  const dExt = (EXT_RATIO[fuel] ?? 0.7) * d0;
  const burnOut = (d0 * d0) / K; // d² law: d² = d0² − K·t
  const tExt = (d0 * d0 - dExt * dExt) / K;
  const flameEnd = extinguishes ? tExt : burnOut;
  const burnTime = extinguishes ? tExt * (1 + FADE) : burnOut; // length of the timeline
  const d = Math.sqrt(Math.max(d0 * d0 - K * Math.min(t, flameEnd), 0));

  // Flame state over the timeline: ignition ramp, steady burn, then out (extinction fade or burnout).
  const ignition = Math.min(t / (IGNITE * burnTime), 1);
  const fade = extinguishes ? Math.max(1 - (t - tExt) / (FADE * tExt), 0) : 1;
  const out = t >= flameEnd - (1.5 * burnTime) / 200; // the time slider snaps to 1/200 steps
  const intensity = out && !extinguishes ? 0 : ignition * (out && extinguishes ? fade : 1);
  const heat = extinguishes && out ? fade : Math.max(intensity, t === 0 ? 0.35 : 0);
  const phase = t === 0 ? "Ready" : t < IGNITE * burnTime ? "Igniting" : !out ? "Burning" : extinguishes ? "Extinguished" : "Burned out";
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
          {info?.trained && info.k_mae_cv != null && info.k_mae_baseline_cv != null && (
            <p className="t-body-s text-center text-fg-2">
              K error {info.k_mae_cv.toFixed(3)} mm²/s, {(info.k_mae_baseline_cv / info.k_mae_cv).toFixed(1)}× smaller
              than always guessing the average ({info.k_mae_baseline_cv.toFixed(3)}).
            </p>
          )}
          <p className="t-caps-s text-center text-fg-3">Microgravity only · FLEX, NASA/TP-2015-216046</p>
        </div>
      </Card>

      {/* Viewport */}
      <section className="glass relative min-h-[560px] overflow-hidden rounded-lg">
        <div aria-hidden className="absolute inset-0 bg-[linear-gradient(rgba(230,232,238,0.04)_1px,transparent_1px),linear-gradient(90deg,rgba(230,232,238,0.04)_1px,transparent_1px)] bg-size-[12.5%_12.5%]" />
        <div className="absolute inset-0">
          <DropletScene
            droplet={Math.max(d * scale * 0.5, 0.004)}
            flame={Math.max(d * STANDOFF * scale * 0.5 * (0.35 + 0.65 * ignition), 0.02)}
            intensity={intensity}
            heat={heat}
            ignition={ignition}
            gravity={gravity}
            labels={labels}
          />
        </div>
        <div className="pointer-events-none absolute top-5 right-5 left-5 flex flex-wrap items-start justify-between gap-3">
          {/* Conditions readout (HUD) */}
          <div className="glass flex flex-col gap-1.5 rounded-md px-3.5 py-2.5">
            <div className="flex items-center gap-2.5">
              <span className="t-caps">ISS droplet chamber</span>
              <Badge tone={phase === "Extinguished" ? "data" : phase === "Burned out" || phase === "Ready" ? "neutral" : "accent"}>{phase}</Badge>
            </div>
            <span className="t-mono-s normal-case text-fg-2">
              {gravity === "micro" ? "~0 g" : "1 g"} · {fuel} · {o2}% O₂ · {pressure} kPa{co2 ? ` · ${co2}% CO₂` : ""}
            </span>
            <span className="t-mono-s normal-case text-fg-2">d = {d.toFixed(2)} mm · K = {K.toFixed(2)} mm²/s</span>
          </div>
          <div className="pointer-events-auto flex flex-col items-end gap-2">
            <div role="radiogroup" aria-label="Gravity" className="glass flex rounded-full p-1">
              {(["micro", "earth"] as const).map((g) => (
                <button
                  key={g} type="button" role="radio" aria-checked={gravity === g} onClick={() => setGravity(g)}
                  className={cx("t-caps-s rounded-full px-3 py-1.5 transition", gravity === g ? "bg-inverse text-fg-inverse" : "text-fg-2 hover:text-fg")}
                >
                  {g === "micro" ? "ISS · microgravity" : "Earth · 1 g"}
                </button>
              ))}
            </div>
            <button type="button" onClick={() => setLabels((v) => !v)} aria-pressed={labels} className="glass t-caps-s rounded-full px-3 py-1.5 text-fg-2 hover:text-fg">
              {labels ? "Hide labels" : "Show labels"}
            </button>
          </div>
        </div>
        {gravity === "earth" && (
          <p className="glass t-body-s pointer-events-none absolute top-[118px] left-5 max-w-[300px] rounded-md px-3.5 py-2.5 text-fg-2">
            Illustration only: on Earth, buoyancy pulls hot gas upward into a tall, sooty flame. The
            model and its numbers cover microgravity (FLEX) only.
          </p>
        )}
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
          <div className="flex flex-col gap-2 rounded-md border border-warn/40 bg-warn/10 px-3.5 py-3">
            <Badge tone="warning" className="self-start">Outside the tested range · extrapolation</Badge>
            {(pred.warnings ?? []).map((w) => (
              <p key={w} className="t-body-s text-fg-2">{w}</p>
            ))}
          </div>
        )}
        <Gauge value={K / 1.2} display={K.toFixed(2)} unit="mm²/s" label="Burn rate K" color="var(--color-accent-default)" />
        <Gauge value={pred?.extinction_probability ?? 0} display={`${Math.round((pred?.extinction_probability ?? 0) * 100)}%`} unit="chance" label="Extinction probability" color="var(--color-data-primary)" />
        <div>
          <Fact label="Droplet diameter" value={`${d.toFixed(2)} mm`} />
          <Fact label="Flame diameter ≈" value={`${(d * STANDOFF).toFixed(1)} mm`} />
          {extinguishes
            ? <Fact label="Flame out at (FLEX median)" value={`d ≈ ${dExt.toFixed(2)} mm · t ≈ ${tExt.toFixed(1)} s`} />
            : <Fact label="Burn time (d² law)" value={`${burnOut.toFixed(1)} s`} />}
          <Fact label="Atmosphere" value={`${o2}% O₂ · ${co2}% CO₂ · ${pressure} kPa`} />
        </div>
        {pred?.nearest_test && <NearestTestCard test={pred.nearest_test} />}
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
