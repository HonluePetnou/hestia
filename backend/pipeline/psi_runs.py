"""BASS, BASS-II and Saffire I-III test runs from the cleaned PSI tables.

Sources: data/bass/ and data/saffire/.

The tables are produced by clean_bass.py, clean_bass2.py and clean_saffire.py from the PSI
"Experimental table" downloads. What the tables don't state stays empty: BASS lists material,
shape and size but no atmosphere or outcome; BASS-II gives oxygen and CO2 but no outcome.
"""

import csv
import re
from pathlib import Path

from app.config import DATA_DIR
from app.models import Gravity, Outcome

BASS = DATA_DIR / "bass" / "bass_clean.csv"
BASS2 = DATA_DIR / "bass" / "bass2_clean.csv"
SAFFIRE = DATA_DIR / "saffire" / "saffire_clean.csv"
PSI_DOI = {"PSI-98": "10.60555/0t15-1z43"}  # Saffire I: missing from the PSI metadata download
SAFFIRE_NAME = {"SAFFIRE-1": "Saffire I", "SAFFIRE-2": "Saffire II", "SAFFIRE-3": "Saffire III"}


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _num(v: str | None) -> float | None:
    try:
        return float(v) if v not in ("", None) else None
    except ValueError:
        return None


def _clean(d: dict) -> dict:
    return {k: v for k, v in d.items() if v not in ("", None)}


def _source(r: dict) -> str:
    doi = r.get("source_doi") or PSI_DOI.get(r.get("source_psi", ""))
    return f"{r.get('source_psi')} experimental table" + (f" (DOI {doi})" if doi else "")


def bass_runs() -> list[dict]:
    """BASS (PSI-26): sample material, shape and size per run; no atmosphere or outcome given."""
    runs = []
    for r in _rows(BASS):
        if r.get("is_test_run", "True").lower() != "true":
            continue
        n = _num(r.get("as_run_number"))
        runs.append(
            {
                # Run numbers repeat in the PSI table (reruns, two sessions numbered 89-91), so the
                # test id is part of the label.
                "run_label": (
                    f"BASS run {int(n)} · test {r['test_id']}"
                    if n is not None
                    else f"BASS test {r['test_id']}"
                ),
                "fuel": r.get("material_raw") or r.get("material_family"),
                "gravity": Gravity.microgravity,
                "outcome": Outcome.unknown,
                "extra": _clean(
                    {
                        "test_id": r.get("test_id"),
                        "test_date": r.get("test_date"),
                        "material_family": r.get("material_family"),
                        "shape": r.get("shape"),
                        "size_cm": _num(r.get("size_cm")),
                        "flow_note": r.get("flow_note"),
                        "source": _source(r),
                    }
                ),
            }
        )
    return runs


def bass2_runs() -> list[dict]:
    """BASS-II (PSI-25): sample, oxygen and CO2 at the start of each run; no outcome given."""
    runs = []
    for r in _rows(BASS2):
        o2 = _num(r.get("o2_initial_mole_fraction"))
        co2 = _num(r.get("co2_initial_mole_fraction"))
        runs.append(
            {
                "run_label": f"BASS-II {r['test_id']}",
                "fuel": r.get("material_raw") or r.get("material_family"),
                "oxygen_percent": round(o2 * 100, 2) if o2 is not None else None,
                "gravity": Gravity.microgravity,
                "outcome": Outcome.unknown,
                "extra": _clean(
                    {
                        "test_date": r.get("test_date"),
                        "material_family": r.get("material_family"),
                        "shape": r.get("shape"),
                        "o2_final_mole_fraction": _num(r.get("o2_final_mole_fraction")),
                        "co2_mole_fraction": co2,
                        "co_final_ppm": _num(r.get("co_final_ppm")),
                        "fan_display": r.get("fan_display_raw"),
                        "source": _source(r),
                    }
                ),
            }
        )
    return runs


def _thickness_mm(r: dict) -> float | None:
    """The cleaned value, else the raw text: '037 mm' is 0.37 mm, '.33 cm' is 3.3 mm."""
    if (v := _num(r.get("thickness_mm"))) is not None:
        return v
    raw = (r.get("thickness_raw") or "").strip()
    m = re.fullmatch(r"(\d*\.?\d+)\s*(mm|cm)", raw)
    if not m:
        return None
    num = m.group(1)
    value = float(f"0.{num[1:]}" if num.startswith("0") and "." not in num else num)
    return round(value * 10 if m.group(2) == "cm" else value, 3)


def _saffire_outcome(r: dict) -> Outcome:
    """Spread when a burn length or spread rate is reported, extinction when the burn length
    is about zero (the silicone samples), unknown otherwise."""
    length = (r.get("burn_length_microgravity_raw") or "").strip()
    rate = (r.get("spread_microgravity_raw") or "").strip()
    if re.fullmatch(r"~?\s*0", length):
        return Outcome.extinction
    if re.search(r"\d", rate) and "n/a" not in rate or re.match(r"~?\s*[1-9]", length):
        return Outcome.spread
    return Outcome.unknown


def saffire_runs() -> list[dict]:
    """Saffire I-III (PSI-98/99/100): large-scale samples burned on Cygnus after leaving the ISS."""
    runs = []
    for r in _rows(SAFFIRE):
        code = r["experiment_code"]
        lo, hi = _num(r.get("o2_mole_fraction_min")), _num(r.get("o2_mole_fraction_max"))
        o2 = (lo + hi) / 2 if lo is not None and hi is not None else lo or hi
        runs.append(
            {
                "run_label": f"{SAFFIRE_NAME.get(code, code)} {r['sample_id']}",
                "fuel": r.get("material_raw") or r.get("material_family") or None,
                "oxygen_percent": round(o2 * 100, 1) if o2 is not None else None,
                "flow_velocity_cm_s": _num(r.get("air_flow_cm_s")),
                "gravity": Gravity.microgravity,
                "outcome": _saffire_outcome(r),
                "extra": _clean(
                    {
                        "flow_direction": r.get("flow_direction"),
                        "thickness_mm": _thickness_mm(r),
                        "sample_length_cm": _num(r.get("length_cm")),
                        "sample_width_cm": _num(r.get("width_cm")),
                        "burn_time_s": _num(r.get("burn_time_s")),
                        "ignition_power_w": _num(r.get("ignition_power_w")),
                        "burn_length_raw": r.get("burn_length_microgravity_raw"),
                        "spread_rate_raw": r.get("spread_microgravity_raw"),
                        "source": _source(r),
                    }
                ),
            }
        )
    return runs
