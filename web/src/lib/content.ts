/**
 * Static content shown in the UI that the API does not provide yet.
 * Items marked SAMPLE are placeholders from the Figma mockups — replace them
 * with real values (from the pipeline / API) during the hackathon.
 */

/** Visual identity per experiment (art strip colors) + short descriptors. */
export const EXPERIMENT_META: Record<string, { art: [string, string]; tagline: string; fuels: string; years: string }> = {
  BASS: { art: ["#FF7A30", "#C2501A"], tagline: "Solids burning", fuels: "PMMA, cotton", years: "2011" },
  SAFFIRE: { art: ["#FF4D4D", "#FF7A30"], tagline: "Spacecraft fire", fuels: "SIBAL, Nomex", years: "2016" },
  SAME: { art: ["#9AA0AE", "#3A3F4D"], tagline: "Smoke detection", fuels: "Teflon, Kapton", years: "2008" },
  FLEX: { art: ["#5AA9FF", "#FF7A30"], tagline: "Droplet extinction", fuels: "n-heptane, methanol", years: "2009" },
  ACME: { art: ["#5AA9FF", "#3A3F4D"], tagline: "Gaseous flames", fuels: "Ethylene, methane", years: "2017" },
};
export const metaFor = (code: string) =>
  EXPERIMENT_META[code.toUpperCase()] ?? { art: ["#FF7A30", "#3A3F4D"] as [string, string], tagline: "Combustion", fuels: "—", years: "—" };

/** Knowledge-base numbers from the Phase 1 pipeline run (make fetch / make extract). */
export const CORPUS = { reports: 37, indexed: 36, flagged: 1, flexTests: "170+" };

/** SAMPLE: approximate first-flight years — verify against NTRS before the demo. */
export const TIMELINE = [
  { code: "FLEX", desc: "Droplet extinction", year: "2009", state: "done" },
  { code: "BASS", desc: "Solids burning", year: "2011", state: "done" },
  { code: "SAFFIRE", desc: "Spacecraft fire", year: "2016", state: "active" },
  { code: "ACME", desc: "Gaseous flames", year: "2017", state: "next" },
] as const;

/** Facts for the Relevance target panel (well-established values). */
export const TARGETS = {
  moon: {
    label: "Moon", gravity: "0.17 g", program: "Artemis",
    facts: [
      ["Gravity", "0.166 g · 1.62 m/s²"],
      ["Proposed habitat air", "56.5 kPa · 34% O₂"],
      ["Lunar day", "≈ 29.5 Earth days"],
    ],
    note: "Oxygen-enriched, low-pressure habitat air plus weak buoyancy: flames may spread where they would die on Earth.",
  },
  mars: {
    label: "Mars", gravity: "0.38 g", program: "Crewed Mars",
    facts: [
      ["Gravity", "0.38 g · 3.71 m/s²"],
      ["Surface pressure", "≈ 0.6 kPa (CO₂)"],
      ["Sol", "24 h 37 min"],
    ],
    note: "Stronger buoyancy than on the Moon, but long missions far from rescue make every cabin fire critical.",
  },
} as const;

/** SAMPLE: AI "key differences" for the Compare screen until /ask can generate them. */
export const COMPARE_POINTS = [
  { text: "Only SAFFIRE burned large samples, closest to a real cabin fire.", ntrsId: "20170000230", page: 3 },
  { text: "FLEX isolates fuel chemistry: no flow, no wall, pure droplet physics.", ntrsId: "20150023456", page: 12 },
  { text: "BASS adds forced flow, which strongly changes whether solids keep burning.", ntrsId: "20160000593", page: 5 },
];

export const ASSISTANT_SUGGESTIONS = [
  "How does flame spread change at lunar gravity?",
  "Compare BASS and Saffire",
  "Which fuels extinguish first?",
  "Smoke detection on Mars",
];

/** "ISS (Microgravity Science Glovebox)" -> "ISS · MSG" (design uses short platform labels). */
export const shortPlatform = (p?: string | null) =>
  (p ?? "").replace(/\s*\(([^)]+)\)/, (_, inner: string) => ` · ${inner.split(/\s+/).map((w) => w[0]).join("").toUpperCase()}`) || "—";

export const ntrsUrl =(id: string) => `https://ntrs.nasa.gov/citations/${id}`;
