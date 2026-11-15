# Data

Large and downloaded files stay out of git. Only this README, the per-source READMEs and the
small hand-made `flex/flex_table_ix.csv` are committed.

| Folder | Source | How to get it | Committed? |
|---|---|---|---|
| `ntrs/` | NASA Technical Reports Server | `make fetch` then `make extract` | README only |
| `psi/` | NASA Physical Sciences Informatics | Manual download (below) | README only |
| `flex/` | FLEX results, NASA/TP-2015-216046 Table IX | Manual transcription (below) | Yes |

All NASA data used here is public domain (NTRS) or CC0 (PSI).

---

## 1. NTRS (scripted)

```bash
make fetch     # = cd backend && uv run python -m pipeline.fetch_ntrs
make extract   # = cd backend && uv run python -m pipeline.extract_text
```

- Search queries live in `backend/pipeline/queries.txt` (one per line). Edit them to widen the corpus.
- Options: `--max-per-query 15`, `--max-total 40`, `--delay 1.0`, `--max-mb 60`, `--no-pdf`.
  Run `uv run python -m pipeline.fetch_ntrs --help` for all options.
- Re-running is safe: PDFs already downloaded are skipped.

Output:

```
ntrs/
├── catalog.csv              id, title, authors, year, url, pdf_url
├── pdf/<id>.pdf
├── text/<id>.jsonl          one line per page: {"page": 1, "text": "..."}
└── extraction_report.csv    ntrs_id, pages, chars, chars_per_page, status
```

In `extraction_report.csv`, `status` is `ok`, `low_text` (probably a scanned PDF: exclude it or
OCR it), `empty` or `error`.

Record page for any document: `https://ntrs.nasa.gov/citations/<id>`.

---

## 2. PSI: Physical Sciences Informatics (manual)

PSI (<https://psi.nasa.gov>) has no documented public API. Download by hand:

1. Open <https://psi.nasa.gov> and browse or search the combustion investigations. If downloads
   ask for an account, register one (it's free).
2. Open each investigation: **BASS** (and BASS-II), **Saffire** (I–VI), **SAME**, **FLEX**
   (FLEX, FLEX-2), **ACME** (its sub-experiments: CLD Flame, E-FIELD Flames, Flame Design, s-Flame, BRE).
3. For each one, download only:
   - the **metadata** (investigation description, PI, platform, DOI), JSON if offered, otherwise
     copy it into `metadata.json`;
   - the **experimental tables** (test matrices, test conditions, results) as CSV/XLSX.
   - **Do not** download raw video, image sequences or large binary sensor dumps.
4. Save them as `psi/<CODE>/` (for example `psi/BASS/metadata.json`, `psi/BASS/test_matrix.csv`).
5. Write down each investigation's DOI. It goes into `experiments.psi_doi`.

---

## 3. FLEX Table IX (extracted automatically)

Source: *NASA/TP-2015-216046*, Table IX, "Results by test number and FLEX identifier"
(NTRS [20150023456](https://ntrs.nasa.gov/citations/20150023456), PDF pages 26–34). The report is
part of the NTRS corpus, so the table is parsed from its extracted text:

```bash
cd backend && uv run python -m pipeline.flex_table   # after make fetch && make extract
```

276 of the 280 tests parse cleanly (rows that don't are logged and skipped, never guessed). The
result, `flex/flex_table_ix.csv`, is committed. Spot-check a few rows against the PDF if you change
the parser.

| Column | Unit / values |
|---|---|
| `test_id` | `FLEX-001` … |
| `fuel` | `n-heptane` or `methanol` |
| `pressure_atm` | atm (converted from mmHg) |
| `o2_mole_fraction`, `co2_mole_fraction`, `n2_mole_fraction`, `he_mole_fraction` | 0–1 |
| `initial_diameter_mm` | mm |
| `extinction_diameter_mm` | mm, empty when the flame did not extinguish or it was not measured |
| `outcome` | `extinction`, `disruption` or `complete_burn` |
| `burn_rate_k_mm2_s` | burning-rate constant K, mm²/s (empty if not reported) |
| `burn_time_s` | s |
| `test_date` | as printed (M/D/YY) |
| `source_page` | PDF page the row was read from |

### Cross-check against the PSI table (`flex/flex_psi_clean.csv`)

`flex_psi_clean.csv` is the official PSI-69 experimental table, cleaned by `pipeline/clean_flex.py`
(points to check are listed in `flex/flex_psi_alertes.csv`). Aligned row by row, it matches Table IX
on all 274 shared tests: same O2, pressure, K, extinction diameter, burn time and outcome. The only
differences:

- Table IX has 2 tests that PSI lacks: `FLEX-216` and `FLEX-230`.
- PSI numbers its tests 1-274 in sequence, while Table IX keeps the report's numbers (with gaps).
  Join the two tables on content, not on the test number.
- PSI gives `193F001` to two different tests (its #70 and #73). Use `test_number` as the key.
- Two PSI burn times (`~6`, `~9`) are approximate and left empty.

The model keeps training on Table IX (276 tests, a superset of PSI's 274 with identical values).

---

## 4. Curated catalog and findings

- `experiments.json`: the five investigations (name, platform, years, fuels, description,
  objectives) plus documented test conditions (Saffire IV/V test matrix). FLEX runs come from the
  CSV above.
- `findings.json`: key findings, each with its NTRS sources (`ntrs_id` + PDF page). Every page
  was checked against the extracted text. `relevance_moon`, `relevance_mars` and `confidence` are
  team judgements (0–1) used by `/ranking`. Add findings here, then run
  `uv run python -m pipeline.ingest --only findings`.
