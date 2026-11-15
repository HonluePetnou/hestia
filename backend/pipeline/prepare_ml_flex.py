"""Prepare the cleaned FLEX data for the prediction model (guide 05).

Run from the backend folder:
    uv run python -m pipeline.prepare_ml_flex

Input  : data/flex/flex_psi_clean.csv      (table cleaned by clean_flex.py)
Outputs: data/flex/flex_ml_ready.csv       (one row per usable run)
         data/flex/flex_ml_ranges.json     (ranges and counts for the model card)

The script keeps only the columns known BEFORE the run. Columns measured during or
after the run (burn time, extinction diameter) are excluded: using them to predict
the outcome would leak information.
"""

import json
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# 1. Paths and settings
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]  # the "hestia" folder
INPUT = ROOT / "data" / "flex" / "flex_psi_clean.csv"
OUTPUT = ROOT / "data" / "flex" / "flex_ml_ready.csv"
RANGES = ROOT / "data" / "flex" / "flex_ml_ranges.json"

NUMERIC_INPUTS = [
    "pressure_atm",
    "o2_mole_fraction",
    "co2_mole_fraction",
    "he_mole_fraction",
    "initial_diameter_mm",
]
EXCLUDED = {
    "burn_time_s": "measured during the run: roughly d0² / K (information leak)",
    "extinction_diameter_mm": "measured during the run (information leak)",
    "test_number": "sequence number, no physical link to the outcome",
    "test_date": "run date, no physical link to the outcome",
    "test_gmt": "run time, no physical link to the outcome",
}

# ---------------------------------------------------------------------------
# 2. Read and select the usable rows
# ---------------------------------------------------------------------------
df = pd.read_csv(INPUT)
total = len(df)

# A row is usable when the fuel and every input are known.
complete = df.dropna(subset=["fuel", *NUMERIC_INPUTS]).copy()
complete["extinction"] = (complete["outcome"] == "extinction").astype(int)
complete["usable_for_regression"] = complete["burn_rate_k_mm2_s"].notna()
complete["usable_for_classification"] = complete["outcome"] != "unknown"

columns = ["test_id", "fuel", *NUMERIC_INPUTS]
columns += ["burn_rate_k_mm2_s", "extinction", "outcome"]
columns += ["usable_for_regression", "usable_for_classification"]
ready = complete[columns]

# ---------------------------------------------------------------------------
# 3. Ranges and counts (for the model card and the "outside range" warning)
# ---------------------------------------------------------------------------
reg = ready[ready["usable_for_regression"]]
cla = ready[ready["usable_for_classification"]]
summary = {
    "source": "data/flex/flex_psi_clean.csv (PSI-69, DOI 10.60555/mbq8-0451)",
    "rows_total": int(total),
    "rows_with_complete_inputs": len(ready),
    "rows_for_regression": len(reg),
    "rows_for_classification": len(cla),
    "extinction_yes": int((cla["extinction"] == 1).sum()),
    "extinction_no": int((cla["extinction"] == 0).sum()),
    "fuels": ready["fuel"].value_counts().to_dict(),
    "input_ranges": {c: [float(ready[c].min()), float(ready[c].max())] for c in NUMERIC_INPUTS},
    "k_mm2_s": {
        "min": float(reg["burn_rate_k_mm2_s"].min()),
        "max": float(reg["burn_rate_k_mm2_s"].max()),
        "mean": round(float(reg["burn_rate_k_mm2_s"].mean()), 4),
    },
    "excluded_columns": EXCLUDED,
    "limits": "ISS microgravity only; no lunar or Martian gravity; tested fuels only",
}

# ---------------------------------------------------------------------------
# 4. Save and report
# ---------------------------------------------------------------------------
ready.to_csv(OUTPUT, index=False, encoding="utf-8")
with open(RANGES, "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
    f.write("\n")

print(f"Runs in total                : {total}")
print(f"Complete inputs              : {len(ready)}")
print(f"Usable (K regression)        : {len(reg)}")
print(f"Usable (classification)      : {len(cla)}")
print(f"Extinction yes / no          : {summary['extinction_yes']} / {summary['extinction_no']}")
for column, (low, high) in summary["input_ranges"].items():
    print(f"  {column:22s} from {low:g} to {high:g}")
print(f"Files written                : {OUTPUT.name}, {RANGES.name}")
