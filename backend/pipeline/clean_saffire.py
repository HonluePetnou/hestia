"""Clean the SAFFIRE-1, -2 and -3 test tables downloaded from PSI.

In these tables the units are written inside the cells ("29 cm", "80 W") and some
values are approximate ("~ 21.5") or text ("Insignificant"). The script splits the
number from its unit, converts to the project's units and keeps the original text in
the *_raw columns. It never invents a value.

Run from the backend folder:
    uv run python -m pipeline.clean_saffire

Inputs : data/psi/SAFFIRE-1|2|3/test_matrix.csv   (raw files, never modified)
Outputs: data/saffire/saffire_clean.csv           (clean table, 3 experiments)
         data/saffire/saffire_alerts.csv          (points to check by hand)
"""

import re
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# 1. File paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]  # the "hestia" folder
PSI_DIR = ROOT / "data" / "psi"
OUTPUT = ROOT / "data" / "saffire" / "saffire_clean.csv"
ALERTS = ROOT / "data" / "saffire" / "saffire_alerts.csv"

# ---------------------------------------------------------------------------
# 2. Settings
# ---------------------------------------------------------------------------
# Columns are renamed by POSITION (the headers have typos and stray spaces).
BASE = [
    "sample_id",
    "material_raw",
    "thickness_raw",
    "length_raw",
    "width_raw",
    "air_flow_raw",
]
EXPERIMENTS = {
    "SAFFIRE-1": {
        "psi_id": "PSI-98",
        "doi": None,  # metadata not downloaded: to fill in
        "columns": BASE
        + ["o2_raw", "ignition_power_raw", "ignition_time_raw", "burn_time_raw"]
        + ["flow_direction", "camera_1", "camera_2"],
        # Units written in the headers, used when the cell has none.
        "units": {
            "thickness": "cm",
            "length": "cm",
            "width": "cm",
            "air_flow": "cm/s",
        },
    },
    "SAFFIRE-2": {
        "psi_id": "PSI-99",
        "doi": "10.60555/2chp-m469",
        "columns": BASE
        + ["o2_raw", "ignition_power_raw", "ignition_time_raw", "burn_time_raw"]
        + ["flow_direction", "burn_length_microgravity_raw", "spread_microgravity_raw"]
        + ["burn_length_1g_raw", "spread_rate_1g_raw", "camera_1", "camera_2"],
        "units": {"width": "cm", "air_flow": "cm/s"},
    },
    "SAFFIRE-3": {
        "psi_id": "PSI-100",
        "doi": "10.60555/040q-4h36",
        "columns": BASE + ["flow_direction", "camera_1", "camera_2"],
        "units": {},
    },
}
# Quantity: (project unit, conversions to that unit)
QUANTITIES = {
    "thickness": ("mm", {"mm": 1.0, "cm": 10.0}),
    "length": ("cm", {"cm": 1.0, "mm": 0.1}),
    "width": ("cm", {"cm": 1.0, "mm": 0.1}),
    "air_flow": ("cm/s", {"cm/s": 1.0}),
    "ignition_power": ("W", {"w": 1.0}),
    "ignition_time": ("s", {"s": 1.0}),
    "burn_time": ("s", {"s": 1.0}),
}
GLOBAL_DEFAULT_UNITS = {
    "ignition_power": "w",
    "ignition_time": "s",
    "burn_time": "s",
}
MEASURE_PATTERN = re.compile(r"^(~)?\s*(\d*\.?\d+)\s*([A-Za-z/]*)$")
O2_PATTERN = re.compile(r"^(~)?\s*(\d+\.?\d*)\s*(?:-|to)?\s*(\d+\.?\d*)?$")
RUN_PATTERN = re.compile(r"^(S\d+|\d+-\d+)$")  # S1, S2... or 2-1, 2-2...
FAMILIES = [
    ("silicone", "Silicone"),
    ("sibal", "SIBAL"),
    ("cotton-fiberglass", "SIBAL"),
    ("pmma", "PMMA"),
    ("nomex", "Nomex"),
]
FINAL_ORDER = [
    "experiment_code",
    "sample_id",
    "material_raw",
    "material_family",
    "thickness_mm",
    "length_cm",
    "width_cm",
    "air_flow_cm_s",
    "o2_mole_fraction_min",
    "o2_mole_fraction_max",
    "o2_approximate",
    "ignition_power_w",
    "ignition_time_s",
    "burn_time_s",
    "flow_direction",
    "thickness_raw",
    "length_raw",
    "width_raw",
    "o2_raw",
    "burn_time_raw",
    "burn_length_microgravity_raw",
    "spread_microgravity_raw",
    "burn_length_1g_raw",
    "spread_rate_1g_raw",
    "gravity",
    "source_psi",
    "source_doi",
]

alerts = []  # points to check


def flag(experiment, sample, column, problem, action):
    """Add one line to the alerts list."""
    alerts.append(
        {
            "experiment_code": experiment,
            "sample_id": sample,
            "column": column,
            "problem": problem,
            "action": action,
        }
    )


def read_measure(text, quantity, header_unit):
    """Split "29 cm" into 29 (converted to the project unit). Returns (value, problem)."""
    if pd.isna(text):
        return None, None
    m = MEASURE_PATTERN.match(text.strip())
    if m is None:
        return None, "non-numeric text"
    number, unit = m.group(2), m.group(3).lower() or header_unit
    if re.match(r"^0\d+$", number):
        return None, f"suspicious leading zero ('{number}': 0.{number[1:]}?)"
    conversions = QUANTITIES[quantity][1]
    if unit not in conversions:
        return None, f"missing or unknown unit ('{unit}')"
    return round(float(number) * conversions[unit], 4), None


def read_o2(text):
    """ "21.5 - 21.7", "~ 22.1" or "22.1 to 22.0" as (min, max, approximate)."""
    if pd.isna(text):
        return None, None, None
    m = O2_PATTERN.match(text.strip())
    if m is None:
        return None, None, None
    a = float(m.group(2))
    b = float(m.group(3)) if m.group(3) else a
    return min(a, b) / 100, max(a, b) / 100, m.group(1) is not None


# ---------------------------------------------------------------------------
# 3. Read and clean each experiment
# ---------------------------------------------------------------------------
tables = []
rows_read = 0
for code, settings in EXPERIMENTS.items():
    raw = pd.read_csv(PSI_DIR / code / "test_matrix.csv", encoding="utf-8-sig", dtype=str)
    assert len(raw.columns) == len(settings["columns"]), f"{code}: unexpected columns"
    raw.columns = settings["columns"]
    rows_read += len(raw)
    for column in raw.columns:
        raw[column] = raw[column].str.replace(r"\s+", " ", regex=True).str.strip()

    # Keep only real test runs (not notes or visualization data).
    is_run = raw["sample_id"].fillna("").map(lambda s: bool(RUN_PATTERN.match(s)))
    for i in raw.index[~is_run]:
        sample = str(raw.loc[i, "sample_id"])[:40]
        flag(code, sample, "sample_id", "row is not a test run", "skipped")
    df = raw[is_run].copy()

    # Numbers and units.
    for quantity, (project_unit, _) in QUANTITIES.items():
        source = f"{quantity}_raw"
        if source not in df.columns:
            continue
        default = settings["units"].get(quantity) or GLOBAL_DEFAULT_UNITS.get(quantity)
        values = []
        for i in df.index:
            value, problem = read_measure(df.loc[i, source], quantity, default)
            text = df.loc[i, source]
            if problem and pd.notna(text) and re.search(r"\d", text):
                flag(code, df.loc[i, "sample_id"], source, f"{problem}: '{text}'", "set to empty")
            values.append(value)
        suffix = project_unit.lower().replace("/", "_")
        df[f"{quantity}_{suffix}"] = values

    # Oxygen (percent in the file, fraction in the project).
    o2 = [read_o2(t) for t in df["o2_raw"]] if "o2_raw" in df.columns else [(None,) * 3] * len(df)
    df["o2_mole_fraction_min"] = [x[0] for x in o2]
    df["o2_mole_fraction_max"] = [x[1] for x in o2]
    df["o2_approximate"] = [x[2] for x in o2]

    df["material_family"] = df["material_raw"].map(
        lambda t: "+".join(dict.fromkeys(n for w, n in FAMILIES if w in str(t).lower())) or None
    )
    df["flow_direction"] = df["flow_direction"].str.lower()
    df["experiment_code"] = code
    df["gravity"] = "microgravity"  # SAFFIRE ran aboard the Cygnus cargo vehicle
    df["source_psi"] = settings["psi_id"]
    df["source_doi"] = settings["doi"]
    if settings["doi"] is None:
        flag(code, None, "source_doi", "unknown DOI (metadata not downloaded)", "to fill in")
    tables.append(df)

clean = pd.concat(tables, ignore_index=True)
for column in FINAL_ORDER:
    if column not in clean.columns:
        clean[column] = None  # column missing from this table: empty cell

# ---------------------------------------------------------------------------
# 4. Save
# ---------------------------------------------------------------------------
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
clean[FINAL_ORDER].to_csv(OUTPUT, index=False, encoding="utf-8")
alert_columns = ["experiment_code", "sample_id", "column", "problem", "action"]
pd.DataFrame(alerts, columns=alert_columns).to_csv(ALERTS, index=False, encoding="utf-8")

# ---------------------------------------------------------------------------
# 5. Short summary
# ---------------------------------------------------------------------------
print(f"Rows read           : {rows_read} ({len(clean)} test runs)")
print(f"Alerts              : {len(alerts)} (see {ALERTS.name})")
print("Runs per experiment :", clean["experiment_code"].value_counts().to_dict())
print("Materials           :", clean["material_family"].value_counts(dropna=False).to_dict())
print(f"Clean file          : {OUTPUT}")
