"""Unit tests for chunking, FLEX parsing, citation verification and the FLEX model.

None of these need a database or an API key.
"""

import pandas as pd

from app.services import flex_model
from app.services.rag import verify_citations
from app.services.retrieval import RetrievedChunk, keyword_query
from pipeline.chunk import MIN_CHUNK_WORDS, chunk_pages, clean_text
from pipeline.flex_table import parse_pages, parse_row


def _chunk(ntrs_id: str, page: int) -> RetrievedChunk:
    return RetrievedChunk(ntrs_id, f"Doc {ntrs_id}", page, "text", f"https://x/{ntrs_id}", 0.9)


# --- chunking ---------------------------------------------------------------


def test_clean_text_joins_hyphenation_and_strips_nul() -> None:
    assert clean_text("micro-\ngravity\x00 flame\n\nspread") == "microgravity flame spread"


def test_chunks_keep_page_numbers_and_respect_size() -> None:
    sentence = "The flame spread slowly along the sample in microgravity conditions. "
    pages = [{"page": 3, "text": sentence * 80}, {"page": 4, "text": sentence * 10}]
    chunks = chunk_pages("123", pages, max_tokens=100, overlap=20)
    assert {c.page for c in chunks} == {3, 4}
    assert all(len(c.content.split()) <= 75 + 10 for c in chunks)  # 100 tokens ~ 75 words
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_tiny_pages_are_dropped() -> None:
    chunks = chunk_pages("1", [{"page": 1, "text": "NASA/TP-2015 page 3"}])
    assert chunks == [] and MIN_CHUNK_WORDS > 3


# --- FLEX Table IX ----------------------------------------------------------

ROW = [
    "20CAL10", "3/5/09", "19:20:06", "Methanol", "762", ".21", ".79", "0", "0",
    "1.86", ".94", ".6", "5", "Extinction",
]  # fmt: skip


def test_parse_flex_row() -> None:
    row = parse_row("002", ROW)
    assert row is not None
    assert row["test_id"] == "FLEX-002" and row["fuel"] == "methanol"
    assert row["o2_mole_fraction"] == 0.21 and row["burn_rate_k_mm2_s"] == 0.6
    assert row["outcome"] == "extinction"
    assert abs(row["pressure_atm"] - 762 / 760) < 1e-3


def test_parse_flex_row_missing_values_and_approximations() -> None:
    tokens = ROW.copy()
    tokens[10], tokens[12] = "�", "~6"  # no extinction diameter, approximate burn time
    row = parse_row("010", tokens)
    assert row is not None
    assert row["extinction_diameter_mm"] is None and row["burn_time_s"] == 6.0


def test_parse_flex_rejects_garbage() -> None:
    assert parse_row("003", ["Fuel", "Ambient", "pressure"]) is None
    rows, failed = parse_pages([{"page": 26, "text": "FLEX‑001 " + " ".join(ROW)}])
    assert [r["test_id"] for r in rows] == ["FLEX-001"] and failed == []


# --- citations --------------------------------------------------------------


def test_verify_citations_keeps_real_and_strips_invented() -> None:
    chunks = [_chunk("20150023456", 12), _chunk("20240002981", 6)]
    text = (
        "Droplets extinguish radiatively [20150023456, p.12]. Smoke is the main hazard "
        "[NTRS-20240002981, page 6]. Fires spread fast on Mars [99999999, p.1]."
    )
    out, cited = verify_citations(text, chunks)
    assert "[20150023456, p.12]" in out and "[20240002981, p.6]" in out
    assert "99999999" not in out
    assert [(c.ntrs_id, c.page) for c in cited] == [("20150023456", 12), ("20240002981", 6)]


def test_verify_citations_rejects_wrong_page() -> None:
    out, cited = verify_citations("Claim [20150023456, p.13].", [_chunk("20150023456", 12)])
    assert cited == [] and "p.13" not in out


def test_keyword_query_drops_stopwords() -> None:
    assert keyword_query("How does the flame spread on the Moon?") == "flame | moon | spread"
    assert keyword_query("what is it?") is None


# --- FLEX model -------------------------------------------------------------


def test_flex_model_trains_and_behaves_physically() -> None:
    model = flex_model.get_model()
    assert model is not None, "data/flex/flex_table_ix.csv should be committed"
    assert model.n_k > 200 and model.k_r2 > 0.5 and model.ext_auc > 0.75

    def pred(o2: float) -> tuple[float, float, bool]:
        return flex_model.predict(model, flex_model.features_row("n-heptane", o2, 101.3, 3.0))

    k_low, p_low, _ = pred(13)
    k_high, p_high, in_range = pred(30)
    assert k_high > k_low  # more oxygen burns faster
    assert p_low > p_high  # and extinguishes less often
    assert in_range
    assert not flex_model.predict(model, flex_model.features_row("methanol", 60, 101.3, 3.0))[2]


def test_load_frame_converts_units(tmp_path) -> None:
    csv = tmp_path / "t.csv"
    pd.DataFrame(
        [
            {
                "fuel": "n-heptane", "pressure_atm": 1.0, "o2_mole_fraction": 0.21,
                "co2_mole_fraction": 0.1, "he_mole_fraction": 0.0,
                "initial_diameter_mm": 3.0, "burn_rate_k_mm2_s": 0.6, "outcome": "extinction",
            }
        ]
    ).to_csv(csv, index=False)  # fmt: skip
    df = flex_model.load_frame(csv)
    row = df.iloc[0]
    assert row["heptane"] == 1 and row["oxygen_percent"] == 21.0
    assert abs(row["pressure_kpa"] - 101.325) < 1e-6 and abs(row["co2_percent"] - 10.0) < 1e-9
