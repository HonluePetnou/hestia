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

## 3. FLEX Table IX (manual transcription)

Source: *NASA/TP-2015-216046*, Table IX: FLEX droplet combustion test results (~170 tests).
Find it on NTRS by searching for the report number.

Transcribe it into `flex/flex_table_ix.csv` (the header is already there):

| Column | Unit / values |
|---|---|
| `test_id` | test identifier as printed |
| `fuel` | e.g. `n-heptane`, `methanol`, `n-decane` |
| `pressure_atm` | atm |
| `o2_mole_fraction` | 0–1 |
| `co2_mole_fraction` | 0–1 |
| `n2_mole_fraction` | 0–1 |
| `initial_diameter_mm` | mm |
| `outcome` | `extinction`, `disruption`, `complete_burn` or `unknown` |
| `burn_rate_k_mm2_s` | burning-rate constant K, mm²/s (leave empty if not reported) |

Tips: split the table between two people and cross-check 10 random rows. Keep units exactly as
listed above; convert if the table uses other units.
