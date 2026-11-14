/**
 * Decorative visuals from the Figma file, rebuilt as SVG / CSS so they stay
 * crisp and themeable: starfield, ember glow, droplet flame, radar, gauges, art strips.
 */

import type { CSSProperties } from "react";

/* Deterministic pseudo-random generator so server and client render the same stars. */
function rng(seed: number) {
  let s = seed;
  return () => (s = (s * 16807) % 2147483647) / 2147483647;
}

export function SpaceBackdrop() {
  const r = rng(7);
  const q = (n: number) => Math.round(n * 10) / 10;
  const stars = Array.from({ length: 110 }, () => ({
    x: q(r() * 1440), y: q(r() * 1024), d: r() < 0.85 ? 0.75 : 1.25, o: q(0.12 + r() * 0.45),
    t: q(2.5 + r() * 5), delay: q(r() * 6),
  }));
  const shooting = [
    { top: "12%", left: "88%", t: "13s", delay: "3s" },
    { top: "30%", left: "70%", t: "19s", delay: "11s" },
  ];
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div
        className="absolute"
        style={{
          left: "36%", top: -260, width: 1100, height: 1100,
          background: "radial-gradient(closest-side, rgba(255,122,48,0.10), rgba(90,169,255,0.05) 45%, rgba(7,8,12,0) 100%)",
        }}
      />
      <svg className="star-field absolute -inset-12 h-[calc(100%+6rem)] w-[calc(100%+6rem)]" viewBox="0 0 1440 1024" preserveAspectRatio="xMidYMid slice">
        {stars.map((s, i) => (
          <circle
            key={i} cx={s.x} cy={s.y} r={s.d} fill="#fff" opacity={s.o} className="star"
            style={{ "--o": s.o, "--t": `${s.t}s`, "--delay": `${s.delay}s` } as CSSProperties}
          />
        ))}
      </svg>
      {shooting.map((s, i) => (
        <span
          key={i} className="shooting-star"
          style={{ top: s.top, left: s.left, "--t": s.t, "--delay": s.delay } as CSSProperties}
        />
      ))}
    </div>
  );
}

/* Spherical droplet flame (Figma: "Hero Visual / Droplet flame"). 600 x 540 artboard. */
export function DropletFlame({ className, showOrbits = true }: { className?: string; showOrbits?: boolean }) {
  const cx = 300, cy = 270;
  return (
    <svg viewBox="0 0 600 540" className={className} role="img" aria-label="Spherical flame around a burning fuel droplet">
      <defs>
        <radialGradient id="df-halo"><stop offset="0" stopColor="#5AA9FF" stopOpacity="0.22" /><stop offset="0.5" stopColor="#5AA9FF" stopOpacity="0.06" /><stop offset="1" stopColor="#07080C" stopOpacity="0" /></radialGradient>
        <radialGradient id="df-shell">
          <stop offset="0" stopColor="#5AA9FF" stopOpacity="0" /><stop offset="0.62" stopColor="#5AA9FF" stopOpacity="0.08" />
          <stop offset="0.86" stopColor="#7FC0FF" stopOpacity="0.85" /><stop offset="0.93" stopColor="#5AA9FF" stopOpacity="0.35" />
          <stop offset="1" stopColor="#5AA9FF" stopOpacity="0" />
        </radialGradient>
        <radialGradient id="df-soot"><stop offset="0" stopColor="#FFB27A" stopOpacity="0.9" /><stop offset="0.35" stopColor="#FF7A30" stopOpacity="0.55" /><stop offset="1" stopColor="#FF7A30" stopOpacity="0" /></radialGradient>
        <radialGradient id="df-drop"><stop offset="0" stopColor="#FFF3E6" /><stop offset="0.6" stopColor="#FFB27A" /><stop offset="1" stopColor="#C2501A" /></radialGradient>
        <filter id="df-glow" x="-200%" y="-200%" width="500%" height="500%"><feGaussianBlur stdDeviation="14" /></filter>
      </defs>
      <circle cx={cx} cy={cy} r={260} fill="url(#df-halo)" />
      <circle cx={cx} cy={cy} r={150} fill="url(#df-shell)" className="flame-breathe" />
      <circle cx={cx} cy={cy} r={85} fill="url(#df-soot)" className="flame-flicker" />
      <circle cx={cx} cy={cy} r={23} fill="#FF7A30" opacity="0.55" filter="url(#df-glow)" className="flame-flicker" />
      <circle cx={cx} cy={cy} r={23} fill="url(#df-drop)" />
      {showOrbits && (
        <>
          <ellipse cx={cx} cy={cy} rx={280} ry={85} fill="none" stroke="rgba(230,232,238,0.14)" transform={`rotate(-14 ${cx} ${cy})`} />
          <g className="orbit-spin-rev">
            <circle cx={cx} cy={cy} r={215} fill="none" stroke="rgba(230,232,238,0.14)" strokeDasharray="2 6" />
          </g>
          <g className="orbit-spin">
            <circle cx={540} cy={214} r={4} fill="#FF7A30" />
            <circle cx={52.5} cy={312.5} r={2.5} fill="#E6E8EE" />
            <circle cx={422} cy={447} r={2} fill="#5AA9FF" />
            <circle cx={181.5} cy={75.5} r={1.5} fill="#E6E8EE" />
          </g>
        </>
      )}
    </svg>
  );
}

/* Moon vs Mars radar (Overview card). */
export function Radar({ dots }: { dots: { x: number; y: number; target: "moon" | "mars"; size?: number }[] }) {
  return (
    <svg viewBox="0 0 208 104" className="h-[104px] w-full" role="img" aria-label="Findings plotted by relevance to Moon and Mars">
      <circle cx="104" cy="52" r="52" fill="none" stroke="rgba(230,232,238,0.14)" />
      <circle cx="104" cy="52" r="35" fill="none" stroke="rgba(230,232,238,0.14)" strokeDasharray="2 4" />
      <circle cx="104" cy="52" r="18" fill="none" stroke="rgba(230,232,238,0.14)" />
      <circle cx="104" cy="52" r="5" fill="var(--color-accent-default)" />
      {dots.map((d, i) => (
        <circle key={i} cx={104 + d.x} cy={52 + d.y} r={(d.size ?? 6) / 2} fill={d.target === "moon" ? "var(--color-target-moon)" : "var(--color-target-mars)"} />
      ))}
    </svg>
  );
}

/* Experiment art strip: soft flame streak on dark glass. */
export function ArtStrip({ colors, className = "h-[84px]" }: { colors: [string, string]; className?: string }) {
  const [a, b] = colors;
  return (
    <div
      aria-hidden
      className={`w-full rounded-md border border-line ${className}`}
      style={{
        background: `radial-gradient(ellipse 48% 22% at 50% 50%, ${a}d9 0%, ${b}59 40%, transparent 100%), #0B0D13`,
      }}
    />
  );
}

/* 270° gauge (Simulator readouts, Dragon-style). */
export function Gauge({ value, display, unit, label, color }: { value: number; display: string; unit: string; label: string; color: string }) {
  const r = 70, c = 85, start = 135, sweep = 270;
  // Rounded so server and browser produce identical attributes (float noise caused hydration mismatches).
  const round = (n: number) => Math.round(n * 100) / 100;
  const polar = (deg: number) => [round(c + r * Math.cos((deg * Math.PI) / 180)), round(79 + r * Math.sin((deg * Math.PI) / 180))];
  const arc = (from: number, to: number) => {
    const [x1, y1] = polar(from), [x2, y2] = polar(to);
    return `M ${x1} ${y1} A ${r} ${r} 0 ${to - from > 180 ? 1 : 0} 1 ${x2} ${y2}`;
  };
  const v = Math.max(0.001, Math.min(1, value));
  return (
    <figure className="flex flex-col items-center gap-1.5">
      <svg viewBox="0 0 170 150" className="w-[170px]" role="img" aria-label={`${label}: ${display} ${unit}`}>
        <path d={arc(start, start + sweep)} stroke="var(--color-bg-surface-raised)" strokeWidth="7" fill="none" strokeLinecap="round" />
        <path d={arc(start, start + sweep * v)} stroke={color} strokeWidth="7" fill="none" strokeLinecap="round" style={{ filter: `drop-shadow(0 0 10px ${color}88)` }} />
        {Array.from({ length: 11 }, (_, i) => {
          const deg = start + (sweep * i) / 10;
          const inner = i % 5 === 0 ? 0.76 : 0.81;
          const [x1, y1] = polar(deg).map((n, k) => round(k === 0 ? c + (n - c) * 0.86 : 79 + (n - 79) * 0.86));
          const [x2, y2] = polar(deg).map((n, k) => round(k === 0 ? c + (n - c) * inner : 79 + (n - 79) * inner));
          return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--color-text-muted)" strokeWidth="1" />;
        })}
        <text x={c} y={86} textAnchor="middle" className="t-data-l" fill="var(--color-text-primary)">{display}</text>
        <text x={c} y={108} textAnchor="middle" className="t-mono-s" fill="var(--color-text-muted)">{unit}</text>
      </svg>
      <figcaption className="t-caps-s text-fg-2">{label}</figcaption>
    </figure>
  );
}

/* Moon / Mars sphere for the Relevance target panel. */
export function Planet({ target }: { target: "moon" | "mars" }) {
  const moon = target === "moon";
  const [hi, mid, lo] = moon ? ["#E9ECF1", "#9AA0AE", "#2A2E38"] : ["#F2B49C", "#C8553D", "#3A1A12"];
  const craters = moon ? [[-40, -30, 17], [30, 20, 11], [-10, 50, 8], [45, -45, 7], [-60, 30, 6]] : [[-30, -20, 14], [35, 30, 9], [10, -50, 6]];
  return (
    <svg viewBox="0 0 396 300" className="w-full" role="img" aria-label={moon ? "The Moon" : "Mars"}>
      <defs>
        <radialGradient id={`pl-glow-${target}`}><stop offset="0" stopColor={mid} stopOpacity="0.16" /><stop offset="1" stopColor="#07080C" stopOpacity="0" /></radialGradient>
        <radialGradient id={`pl-body-${target}`} cx="0.4" cy="0.4" r="0.65"><stop offset="0" stopColor={hi} /><stop offset="0.55" stopColor={mid} /><stop offset="1" stopColor={lo} /></radialGradient>
      </defs>
      <circle cx="198" cy="150" r="170" fill={`url(#pl-glow-${target})`} />
      <circle cx="198" cy="150" r="110" fill={`url(#pl-body-${target})`} />
      {craters.map(([x, y, rr], i) => <circle key={i} cx={198 + x} cy={150 + y} r={rr} fill="#3A3F4D" opacity={0.15} />)}
      <ellipse cx="198" cy="150" rx="190" ry="55" fill="none" stroke="rgba(230,232,238,0.14)" transform="rotate(12 198 150)" />
      <circle cx="358" cy="110" r="4" fill="#FF7A30" style={{ filter: "drop-shadow(0 0 8px #FF7A30)" }} />
    </svg>
  );
}
