# Space Apps 2026 submission: form fields (copy and paste)

Deadline: **Sunday 15 November 2026, 11:59 p.m. local time.** Then tick "Terms and Conditions",
tick "Confirm All Work is Original", click **Submit for Judging**, and wait for the confirmation banner.

---

## Project Name

Hestia: Guarding the Flame Beyond Earth

## High-Level Project Summary

Hestia turns decades of NASA microgravity combustion research into answers that mission
designers can use. It is an AI assistant, an experiment explorer and a 3D simulator built only on
NASA data. Ask a question about fire in space and Hestia answers from NASA technical reports and
Physical Sciences Informatics investigations, citing the exact page of each source. Explore
FLEX, BASS, BASS-II and Saffire test runs, compare experiments and rank findings by relevance to
the Moon or Mars. Then set fuel, oxygen, pressure and droplet size in the simulator: a model
trained on 276 ISS droplet tests predicts the burning rate and the chance the flame goes out,
shows the closest real NASA test, and warns when you leave the tested range. It addresses the
challenge because fire safety for lunar and Martian habitats depends on lessons NASA already
learned, which today are scattered across hundreds of reports and tables.

## Link to Project Demo

TODO: public link to the 7-slide deck (PDF) or the video of 30 seconds or less.
Must open without login (test it in a private window).

## Link to Final Project

https://github.com/HonluePetnou/hestia

## Detailed Project Description

**What it does**

- **Ask (RAG assistant).** Questions in English or French are answered only from indexed NASA
  sources: 55 NTRS technical reports, 24 PSI investigations and NASA resource pages. Every
  claim carries a citation such as `[NTRS-20190000000, p.4]` that opens the PDF at that page.
  When the sources do not cover a question, Hestia says so instead of inventing an answer.
- **Explore.** Experiment pages for FLEX, BASS, BASS-II, SAME and Saffire with 544 test runs
  from the PSI experimental tables, curated findings with verified page citations, a side-by-side
  comparison of experiments, and a Moon / Mars relevance ranking.
- **Simulate.** A 3D combustion chamber: a fuel droplet burns and shrinks following the d² law
  at the burning rate the model predicts, and goes out where FLEX data says it should. Toggle
  Earth (1 g) and ISS (microgravity) to see the flame stretch or stay spherical. The simulator
  shows the matching NASA test (for methanol at 12 % O₂ it predicts extinction at 2.52 mm; the
  real ISS test FLEX-086 went out at 2.56 mm).
- **Search.** A Ctrl/⌘ K palette finds experiments, findings, report passages and test runs
  instantly, even without the AI.

**How it works**

NASA PDFs and tables are downloaded, cleaned, split into passages and embedded. Retrieval is
hybrid: vector search (pgvector) and full-text search are fused, filtered by a calibrated
relevance threshold, then a Gemini model writes the answer from numbered passages. The backend
rebuilds and checks every citation. The prediction model is a ridge regression for the burning
rate K and a logistic regression for extinction, trained only on FLEX data: its K error is 2.3
times smaller than a naive baseline (MAE 0.047 vs 0.107 mm²/s) and its extinction balanced
accuracy is 0.78 vs 0.50.

**Benefits**

Engineers, students and mission planners get trusted, cited answers in seconds instead of days
of reading, and can test "what if" atmospheres against real ISS data. Hestia is honest about its
limits: out-of-range inputs are flagged as extrapolation.

**What we hope to achieve**

A living fire-safety knowledge base for Artemis and Mars habitat design, extended next to solid
materials (BASS-II, Saffire), partial gravity and smoke detection data.

**Tools**

Python 3.12, FastAPI, PostgreSQL 16 + pgvector, SQLAlchemy, scikit-learn, pandas, PyMuPDF;
Next.js, React, TypeScript, Tailwind CSS, Three.js (React Three Fiber), Recharts; Google Gemini
API (embeddings and answers); Docker; GitHub.

## Use of Super Intelligence (SI)

Yes.

- **In the product:** Google Gemini (`gemini-embedding-001` for embeddings, Gemini Flash Lite
  models for answers) generates the assistant's answers, always from retrieved NASA passages
  with citations checked by our backend. Answers are shown in the app as AI-generated.
- **In development:** we used Claude Code (Anthropic) as a coding assistant to write and review
  parts of the code, tests and documentation, and to draft the pitch text. The idea, the data
  choices and the design decisions are the team's.
- No NASA logos, flags or mission identifiers were generated or modified.

## NASA Data

- **NASA Technical Reports Server (NTRS):** 55 microgravity combustion reports (FLEX, BASS,
  Saffire, SAME, ACME and related studies), indexed page by page for retrieval and citation.
- **NASA Physical Sciences Informatics (PSI):** 24 investigations, including the experimental
  tables of FLEX (PSI-69, DOI 10.60555/mbq8-0451), BASS (PSI-26, DOI 10.60555/58h4-dy80),
  BASS-II (PSI-25, DOI 10.60555/4qc4-de67), Saffire I (PSI-98, DOI 10.60555/0t15-1z43),
  Saffire II (PSI-99, DOI 10.60555/2chp-m469) and Saffire III (PSI-100, DOI 10.60555/040q-4h36).
- **FLEX Table IX** (droplet test conditions and outcomes), used to train and check the model.
- NASA web resources on spacecraft fire safety, used as additional retrieval sources.

## Space Agency Partner Data and Other References

No partner-agency data. Open-source software only (licenses: MIT, Apache 2.0, BSD, PostgreSQL).
All 3D visuals are drawn in code; no third-party images.
