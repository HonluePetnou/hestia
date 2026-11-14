"""Extract FLEX Table IX (NASA/TP-2015-216046, NTRS 20150023456) into data/flex/flex_table_ix.csv.

Usage (from backend/):
    uv run python -m pipeline.flex_table

Reads the per-page text produced by `pipeline.extract_text` (pages 26-34 hold the
table) and writes one CSV row per FLEX test. Rows that do not parse cleanly are
reported and skipped, never guessed. Spot-check a few rows against the PDF after
running it.
"""

import argparse
import csv
import logging
import re
from pathlib import Path

from app.config import DATA_DIR
from pipeline.chunk import read_pages

log = logging.getLogger("flex_table")

NTRS_ID = "20150023456"
SOURCE_PAGES = range(26, 35)  # 1-based PDF pages that hold Table IX
MMHG_PER_ATM = 760.0

COLUMNS = [
    "test_id",
    "fuel",
    "pressure_atm",
    "o2_mole_fraction",
    "co2_mole_fraction",
    "n2_mole_fraction",
    "he_mole_fraction",
    "initial_diameter_mm",
    "extinction_diameter_mm",
    "outcome",
    "burn_rate_k_mm2_s",
    "burn_time_s",
    "test_date",
    "source_page",
]

_ROW_START = re.compile(r"^FLEX\W(\d{3})$")
_DATE = re.compile(r"^\d{1,2}/\d{1,2}/\d{2}$")
_TIME = re.compile(r"^\d{1,2}:\d{2}:\d{2}$")
_OUTCOMES = {"extinction": "extinction", "disruption": "disruption", "completion": "complete_burn"}
_FUELS = {"methanol", "heptane"}
_MISSING = {"�", "-", "–", "—"}


def _num(token: str) -> float | None:
    if token in _MISSING:
        return None
    return float(token.lstrip("~"))  # "~6" marks an approximate value in the table


def parse_row(test_no: str, tokens: list[str]) -> dict | None:
    """Parse the tokens following 'FLEX-NNN'. Expected layout:
    identifier, date, time, fuel, P(mmHg), O2, N2, CO2, He, D0, Dext, K, burn time, test end.
    """
    if len(tokens) < 14:
        return None
    tokens = tokens[:14]
    _ident, date, time, fuel, p, o2, n2, co2, he, d0, dext, k, tb, end = tokens
    if not _DATE.match(date) or not (_TIME.match(time) or time in _MISSING):
        return None
    if fuel.lower() not in _FUELS or end.lower() not in _OUTCOMES:
        return None
    try:
        pressure = _num(p)
        row = {
            "test_id": f"FLEX-{test_no}",
            "fuel": "n-heptane" if fuel.lower() == "heptane" else "methanol",
            "pressure_atm": round(pressure / MMHG_PER_ATM, 4) if pressure else None,
            "o2_mole_fraction": _num(o2),
            "n2_mole_fraction": _num(n2),
            "co2_mole_fraction": _num(co2),
            "he_mole_fraction": _num(he),
            "initial_diameter_mm": _num(d0),
            "extinction_diameter_mm": _num(dext),
            "burn_rate_k_mm2_s": _num(k),
            "burn_time_s": _num(tb),
            "outcome": _OUTCOMES[end.lower()],
            "test_date": date,
        }
    except ValueError:
        return None
    fractions = [row[c] for c in ("o2_mole_fraction", "n2_mole_fraction", "co2_mole_fraction")]
    if any(f is None or not 0 <= f <= 1 for f in fractions):
        return None
    return row


def parse_pages(pages: list[dict]) -> tuple[list[dict], list[str]]:
    """Return (rows, test ids that failed to parse)."""
    rows: list[dict] = []
    failed: list[str] = []
    for p in pages:
        if p["page"] not in SOURCE_PAGES:
            continue
        tokens = p["text"].split()
        starts = [(i, m.group(1)) for i, t in enumerate(tokens) if (m := _ROW_START.match(t))]
        for n, (i, test_no) in enumerate(starts):
            end = starts[n + 1][0] if n + 1 < len(starts) else len(tokens)
            row = parse_row(test_no, tokens[i + 1 : end])
            if row is None:
                failed.append(f"FLEX-{test_no}")
            else:
                row["source_page"] = p["page"]
                rows.append(row)
    # keep the first occurrence of each test id
    seen: set[str] = set()
    unique = [r for r in rows if not (r["test_id"] in seen or seen.add(r["test_id"]))]
    return unique, failed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--in", dest="src", type=Path, default=DATA_DIR / "ntrs" / "text" / f"{NTRS_ID}.jsonl"
    )
    parser.add_argument("--out", type=Path, default=DATA_DIR / "flex" / "flex_table_ix.csv")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if not args.src.exists():
        raise SystemExit(f"{args.src} not found. Run `make fetch` and `make extract` first.")
    rows, failed = parse_pages(read_pages(args.src))
    with args.out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    log.info("Wrote %d FLEX tests to %s", len(rows), args.out)
    if failed:
        log.warning("Skipped %d rows that did not parse: %s", len(failed), ", ".join(failed))


if __name__ == "__main__":
    main()
