"""Turn the FLEX test table into a short, factual text summary the RAG can retrieve.

The assistant only searches text, so questions answered by the test table itself ("which fuel
goes out first?", "lowest oxygen that still burned?") found nothing. This writes plain sentences
with the counts and medians computed from data/flex/flex_table_ix.csv (FLEX Table IX,
NASA/TP-2015-216046), as one more resource document.

Usage: python3 scripts/summarize_tests.py   (then rebuild: python3 scripts/build_corpus.py)
"""

import os

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(ROOT, "..", "flex", "flex_table_ix.csv")
OUT = os.path.join(ROOT, "docs", "resources", "10_flex_test_table_summary.md")
REPORT = "https://ntrs.nasa.gov/api/citations/20150023456/downloads/20150023456.pdf"

OUTCOME = {"extinction": "flame extinction", "disruption": "droplet disruption", "complete_burn": "complete burn"}


def pct(n, d):
    return f"{round(100 * n / d)}%" if d else "n/a"


def main():
    t = pd.read_csv(CSV)
    t["o2"] = (t["o2_mole_fraction"] * 100).round(0)
    t["co2"] = (t["co2_mole_fraction"].fillna(0) * 100).round(0)
    t["he"] = (t["he_mole_fraction"].fillna(0) * 100).round(0)
    t["kpa"] = (t["pressure_atm"] * 101.325).round(0)
    ext = t["outcome"] == "extinction"
    lines = [
        "---",
        "doc_id: flex-test-table-summary",
        'title: "FLEX test table summary (Table IX, NASA/TP-2015-216046): outcomes, oxygen, burning rates"',
        f"source_url: {REPORT}#page=26",
        "source_type: nasa_data_summary",
        "publisher: Computed by Hestia from FLEX Table IX (NASA/TP-2015-216046, NTRS 20150023456)",
        "tags: [FLEX, droplet, extinction, oxygen, methanol, n-heptane, burning rate, CO2, helium, test table]",
        "---",
        "",
        "# FLEX droplet tests: what the test table shows",
        "",
        f"Counts and medians computed from the {len(t)} FLEX droplet tests listed in Table IX of "
        "NASA/TP-2015-216046 (ISS, Combustion Integrated Rack, Multi-user Droplet Combustion "
        "Apparatus, March 2009 to December 2011). Fuels: methanol and n-heptane.",
        "",
        "## Outcomes by fuel",
    ]
    for fuel, g in t.groupby("fuel"):
        counts = g["outcome"].value_counts()
        parts = ", ".join(f"{OUTCOME.get(o, o)} {n} ({pct(n, len(g))})" for o, n in counts.items())
        lines.append(f"- {fuel}: {len(g)} tests; {parts}.")
    m, h = t[t.fuel == "methanol"], t[t.fuel == "n-heptane"]
    lines += [
        "",
        f"Which fuel extinguishes more often: in FLEX, {pct((m.outcome == 'extinction').sum(), len(m))} "
        f"of methanol tests ended in flame extinction versus {pct((h.outcome == 'extinction').sum(), len(h))} "
        "of n-heptane tests. n-heptane droplets were more often disrupted (the droplet broke apart or "
        "the test ended early) than methanol droplets.",
        "",
        "## Extinction diameter (how small the droplet was when the flame went out)",
    ]
    e = t[ext & t.extinction_diameter_mm.notna() & (t.extinction_diameter_mm > 0)].copy()
    e["ratio"] = e.extinction_diameter_mm / e.initial_diameter_mm
    for fuel, g in e.groupby("fuel"):
        q = g["ratio"].quantile([0.25, 0.5, 0.75]).round(2)
        lines.append(
            f"- {fuel}: over {len(g)} extinction tests, the flame went out when the droplet had shrunk "
            f"to a median {q[0.5]} of its initial diameter (middle half {q[0.25]} to {q[0.75]})."
        )
    lines += [
        "",
        "n-heptane flames therefore went out much earlier in the burn (at a larger droplet) than "
        "methanol flames, which typically burned until the droplet was a bit over half its size.",
        "",
        "## Oxygen level and outcome",
    ]
    for fuel, g in t.groupby("fuel"):
        lit = g[g.outcome != "extinction"]
        lines.append(
            f"- {fuel}: tests span {g.o2.min():.0f}% to {g.o2.max():.0f}% oxygen; the lowest oxygen "
            f"at which a test did not end in flame extinction was {lit.o2.min():.0f}%."
        )
        bins = pd.cut(g.o2, [0, 15, 18, 21, 100], labels=["15% O2 or less", "16-18% O2", "19-21% O2", "above 21% O2"])
        for b, gb in g.groupby(bins, observed=True):
            lines.append(f"  - {b}: {len(gb)} tests, {pct((gb.outcome == 'extinction').sum(), len(gb))} ended in extinction.")
    lines += ["", "Lower oxygen made extinction more likely for both fuels.", "", "## Burning rate K"]
    for fuel, g in t[t.burn_rate_k_mm2_s.notna()].groupby("fuel"):
        lines.append(f"- {fuel}: median burning-rate constant K = {g.burn_rate_k_mm2_s.median():.2f} mm²/s over {len(g)} tests.")
    k = t[t.burn_rate_k_mm2_s.notna()]
    lo, hi = k[k.o2 <= 16], k[k.o2 >= 21]
    lines += [
        f"- Across both fuels, median K was {lo.burn_rate_k_mm2_s.median():.2f} mm²/s at 16% oxygen "
        f"or less versus {hi.burn_rate_k_mm2_s.median():.2f} mm²/s at 21% or more: droplets burn faster "
        "in richer oxygen.",
        "",
        "## Diluents and pressure",
    ]
    co2, he, n2 = t[t.co2 > 0], t[t.he > 0], t[(t.co2 == 0) & (t.he == 0)]
    lines += [
        f"- Carbon dioxide (CO2) was added in {len(co2)} tests ({co2.co2.min():.0f}% to {co2.co2.max():.0f}% CO2); "
        f"{pct((co2.outcome == 'extinction').sum(), len(co2))} of them ended in extinction, versus "
        f"{pct((n2.outcome == 'extinction').sum(), len(n2))} of the nitrogen-only tests.",
        f"- Helium was added in {len(he)} tests ({he.he.min():.0f}% to {he.he.max():.0f}% He); median K "
        f"{he.burn_rate_k_mm2_s.median():.2f} mm²/s versus {n2.burn_rate_k_mm2_s.median():.2f} mm²/s "
        "in nitrogen-only atmospheres.",
        f"- Pressure ranged from {t.kpa.min():.0f} to {t.kpa.max():.0f} kPa "
        f"({t.pressure_atm.min():.2f} to {t.pressure_atm.max():.2f} atm).",
        "",
        "All figures are descriptive statistics of the published test table, not model predictions.",
    ]
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
