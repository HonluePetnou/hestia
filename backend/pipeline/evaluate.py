"""Quality evaluation of retrieval and answers on data/eval/questions.json.

    uv run python -m pipeline.evaluate                    # retrieval + answers (calls the LLM)
    uv run python -m pipeline.evaluate --retrieval-only   # embeddings only, no generation
    uv run python -m pipeline.evaluate --calibrate        # similarity stats to choose the threshold
    uv run python -m pipeline.evaluate --out report.json

Metrics (printed and saved):
  source_recall        expected source present in the retrieved passages (questions with sources)
  term_relevance       share of expected terms found in the retrieved passages (proxy for relevance)
  citation_validity    share of the model's citations that match a passage really sent to it
  unsourced_rate       share of answer sentences with no citation (answers only)
  ungrounded_numbers   numbers in the answer absent from the retrieved passages (fidelity proxy)
  abstention_ok        out-of-corpus questions correctly answered with insufficient_data
  false_abstention     answerable questions wrongly answered with insufficient_data
These are automatic proxies: read the report, and check a sample of answers by hand.
"""

import argparse
import json
import re
import statistics
from pathlib import Path

from app.config import DATA_DIR, get_settings
from app.db import SessionLocal
from app.services import rag, retrieval

QUESTIONS = DATA_DIR / "eval" / "questions.json"
_NUMBER = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?")
# a citation as written by the backend: [PSI-159], [20150023456, p.12], [PASSAGE 2]
_CITE = re.compile(r"\[(?:(?:PASSAGE|P)\s*\d+[^\[\]]*|[A-Za-z0-9][\w\-.]{0,63}(?:, p\.\d+)?)\]")


def load_questions(path: Path = QUESTIONS) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["questions"]


def term_relevance(chunks: list[retrieval.RetrievedChunk], terms: list[str]) -> float | None:
    if not terms:
        return None
    blob = " ".join(c.content.lower() for c in chunks)
    return sum(t.lower() in blob for t in terms) / len(terms)


def unsourced_rate(answer: str) -> float:
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", answer) if len(s.split()) > 3]
    if not sentences:
        return 0.0
    return sum(1 for s in sentences if not _CITE.search(s)) / len(sentences)


def ungrounded_numbers(answer: str, chunks: list[retrieval.RetrievedChunk]) -> list[str]:
    blob = " ".join(c.content for c in chunks).replace(",", ".")
    text = _CITE.sub("", answer).replace(",", ".")
    return sorted({n for n in _NUMBER.findall(text) if n not in blob})


def evaluate(session, questions: list[dict], retrieval_only: bool = False) -> dict:
    rows = []
    for q in questions:
        chunks = retrieval.search(session, q["question"])
        sources = {c.ntrs_id for c in chunks}
        expected = set(q["expected_sources"])
        row = {
            "id": q["id"],
            "behavior": q["expected_behavior"],
            "retrieved": [c.ntrs_id for c in chunks],
            "top_score": max((c.score for c in chunks), default=0.0),
            "source_hit": bool(expected & sources) if expected else None,
            "term_relevance": term_relevance(chunks, q["expected_terms"]),
        }
        if not retrieval_only:
            res = rag.grounded_completion(q["question"], chunks)
            row |= {
                "answer": res.answer,
                "insufficient": res.insufficient_data,
                "n_citations": len(res.citations),
                "citation_refs": res.raw_citation_refs,
                "invalid_citation_refs": res.invalid_citation_refs,
                "unsourced_rate": unsourced_rate(res.answer),
                "ungrounded_numbers": ungrounded_numbers(res.answer, chunks),
            }
        rows.append(row)
    return {"rows": rows, "summary": summarize(rows, retrieval_only)}


def _mean(values: list[float]) -> float | None:
    return round(statistics.mean(values), 3) if values else None


def summarize(rows: list[dict], retrieval_only: bool) -> dict:
    answerable = [r for r in rows if r["behavior"] != "insufficient"]
    summary = {
        "questions": len(rows),
        "source_recall": _mean(
            [float(r["source_hit"]) for r in rows if r["source_hit"] is not None]
        ),
        "term_relevance": _mean(
            [r["term_relevance"] for r in rows if r["term_relevance"] is not None]
        ),
        "retrieval_threshold": get_settings().retrieval_min_score,
    }
    if not retrieval_only:
        ooc = [r for r in rows if r["behavior"] == "insufficient"]
        full = [r for r in rows if r["behavior"] == "answer"]
        answered = [r for r in rows if not r["insufficient"]]
        summary |= {
            "citation_validity": (
                round(1 - sum(r["invalid_citation_refs"] for r in answered) / refs, 3)
                if (refs := sum(r["citation_refs"] for r in answered))
                else None
            ),
            "unsourced_rate": _mean([r["unsourced_rate"] for r in answered]),
            "answers_with_ungrounded_numbers": sum(1 for r in answered if r["ungrounded_numbers"]),
            "abstention_ok": _mean([float(r["insufficient"]) for r in ooc]),
            "false_abstention": _mean([float(r["insufficient"]) for r in full]),
        }
    else:
        ooc = [r for r in rows if r["behavior"] == "insufficient"]
        summary["out_of_corpus_with_no_passage"] = _mean([float(not r["retrieved"]) for r in ooc])
    summary["answerable_questions"] = len(answerable)
    return summary


def calibrate(session, questions: list[dict]) -> dict:
    """Top-1 cosine similarity of answerable vs out-of-corpus questions (threshold off)."""
    from app.services.llm import MockProvider, get_embedder

    if isinstance(get_embedder(), MockProvider):
        raise SystemExit("Calibration needs a real embedding provider (LLM_PROVIDER != mock).")
    top = {"answerable": [], "out_of_corpus": []}
    for q in questions:
        hits = retrieval.search(session, q["question"], k=1, apply_threshold=False)
        score = hits[0].score if hits else 0.0
        top["out_of_corpus" if q["expected_behavior"] == "insufficient" else "answerable"].append(
            score
        )
    lo, hi = (min(top["answerable"], default=0), max(top["out_of_corpus"], default=0))
    return {
        "top1_scores": {k: sorted(round(s, 3) for s in v) for k, v in top.items()},
        "answerable_min": round(lo, 3),
        "out_of_corpus_max": round(hi, 3),
        "suggested_min_score": round((lo + hi) / 2, 3) if lo > hi else None,
        "note": (
            "Pick RETRIEVAL_MIN_SCORE between out_of_corpus_max and answerable_min. If they "
            "overlap (suggested_min_score is null) no single threshold separates the sets: keep "
            "the threshold low and rely on the model's insufficient_data."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--retrieval-only", action="store_true")
    parser.add_argument("--calibrate", action="store_true")
    parser.add_argument("--questions", type=Path, default=QUESTIONS)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    questions = load_questions(args.questions)
    with SessionLocal() as session:
        result = (
            calibrate(session, questions)
            if args.calibrate
            else evaluate(session, questions, args.retrieval_only)
        )
    text = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(json.dumps(result.get("summary", result), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
