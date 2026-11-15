# RAG corpus — NASA Space Apps 2026 « Flame in Freefall »

Built from the challenge's Resources tab (https://www.spaceappschallenge.org/2026/challenges/flame-in-freefall/?tab=resources) and the PSI investigation pages it points to. Collected on 2026-11-13.

## Contents

```
out/chunks.jsonl          <- READY TO INDEX: 323 chunks (1 JSON per line), text + metadata
out/investigations.json   <- 24 PSI investigations, structured (for the dashboard: filters, ranking)
out/investigations.csv    <- same thing, flat (Excel / pandas)
out/psi_md/*.md           <- 1 readable markdown file per investigation
docs/resources/*.md       <- challenge statement + the 9 other resources (Apollo 1/13, Mir, spinoffs, Glenn, guide, video)
docs/psi/batch*.json      <- raw PSI extracts (source of truth)
docs/psi/annotations_curated.json <- MY annotations (tier, pillars, cross-refs) — not NASA text
scripts/build_corpus.py   <- rebuilds out/ (python3 scripts/build_corpus.py --max-chars 1800)
```

## Chunk format (chunks.jsonl)
```json
{"chunk_id":"psi-69#02","doc_id":"psi-69","psi_id":"PSI-69","acronym":"FLEX","section":"approach",
 "source_url":"https://psi.nasa.gov/...","doi":"10.60555/...","fuel_category":"liquid droplets",
 "hardware":["CIR","MDCA"],"fire_safety_tier":1,"pillars":["suppression","prevention"],
 "text":"[PSI-69 FLEX] Flame Extinguishment Experiment ... \nSection: approach\n..."}
```
Every chunk text starts with a context header (ID, title, fuel type, hardware), so it stays useful when retrieved on its own. Use `psi_id`, `fuel_category`, `pillars` and `fire_safety_tier` as metadata filters in the vector DB.

## The 24 investigations
- Tier 1 (named explicitly as fire safety in the challenge): BASS (PSI-26), BASS-II (25), SAFFIRE-I/II/III (98/99/100), SAME (102), SAME-R (101), FLEX (69), ACME BRE (20)
- Tier 2: FLEX-2 (68), DAFT/DAFT-2 (47), CFI-G (159), E-FIELD (22), SPICE (107), BASS-FGM modeling (62), SAME smoke modeling (115)
- Tier 3: CFI (39), Flame Design (10), CLD Flame (21), s-Flame (23), SLICE (106), SPICE analysis (60), cool flame CFD (117), cool flame counterflow (142)
Not included: PSI-181 (solders) and PSI-108 (STDCE, fluid physics), which come up in the "combustion" search but are off-topic.

## Completed on 2026-11-13 (Hestia)
- **Verbatim PSI text for 15 investigations** (PSI-10, 20, 21, 22, 23, 39, 47, 60, 62, 106, 107, 115, 117, 142, 159): objectives, approach, hypothesis and impacts re-copied word for word from the official PSI pages, with corrected dates, dataset sizes, sub-research areas and experimental-table row counts. Stored in `docs/psi/verbatim_overrides*.json`; `build_corpus.py` applies them over `batch*.json`. Their publication lists are now complete.
- **Researcher's Guide, full text**: the 2015 PDF (downloaded from nasa.gov, 56 pages) extracted page by page into `docs/resources/09_researchers_guide_full.md`. The PDF itself goes in `docs/pdf/` (gitignored).
- Rebuilt corpus: 24 investigations, 323 chunks.

## Known limitations / what to add
1. **Full experimental tables are not included.** PSI shows only 5 rows per page and does not answer automated requests from this machine, so the CSVs have to be downloaded by hand from each investigation's "Experimental table" folder. Row counts on PSI: CFI-G 1016, SPICE 470, FLEX 275, Flame Design 208, BASS-II 130, CFI 88, CLD Flame 33, E-FIELD 33, ACME BRE 19, s-Flame 19, PSI-142 9, DAFT 3.
2. **NASA Glenn PDFs** (ACME, BASS, DAFT, FLEX, Saffire, SAME, SLICE, SPICE): links are in `docs/resources/02_*.md`, not ingested.
3. **YouTube video**: summary only, no transcript.
4. Publication lists of the 9 tier-1 investigations stay **partial** (FLEX lists 51 and FLEX-2 lists 44 on PSI).
5. `annotations_curated.json` (tier, pillars, habitat relevance) holds the original author's judgment, not NASA text. `habitat_relevance` notes such as "up to 85% O2 per challenge statement" come from the challenge text, not from the PSI page.

License: PSI data is CC0-1.0. Cite the DOIs (NASA SMD Open Source Science requirement, as stated on the PSI site).
