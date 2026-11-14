"""Fetch NTRS search results and PDFs.

Usage (from backend/):
    uv run python -m pipeline.fetch_ntrs [--max-per-query 15] [--max-total 40]

Writes data/ntrs/catalog.csv and data/ntrs/pdf/<id>.pdf.
API: https://ntrs.nasa.gov/api/openapi/
"""

import argparse
import csv
import logging
import re
import time
from pathlib import Path
from typing import Any

import httpx

from app.config import DATA_DIR

BASE_URL = "https://ntrs.nasa.gov"
SEARCH_URL = f"{BASE_URL}/api/citations/search"
QUERIES_FILE = Path(__file__).with_name("queries.txt")
OUT_DIR = DATA_DIR / "ntrs"
CATALOG_FIELDS = ["id", "title", "authors", "year", "url", "pdf_url"]

log = logging.getLogger("fetch_ntrs")


def read_queries(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [q.strip() for q in lines if q.strip() and not q.startswith("#")]


def request_with_retries(
    client: httpx.Client, method: str, url: str, retries: int = 4, **kwargs: Any
) -> httpx.Response:
    """HTTP request with exponential backoff on network errors, 429 and 5xx."""
    for attempt in range(retries + 1):
        try:
            resp = client.request(method, url, **kwargs)
            if resp.status_code < 500 and resp.status_code != 429:
                resp.raise_for_status()
                return resp
            log.warning("HTTP %s for %s", resp.status_code, url)
        except httpx.TransportError as exc:
            log.warning("Network error for %s: %s", url, exc)
        if attempt < retries:
            wait = 2**attempt
            log.info("Retrying in %ss (%s/%s)", wait, attempt + 1, retries)
            time.sleep(wait)
    raise RuntimeError(f"Giving up on {url} after {retries + 1} attempts")


def pdf_link(result: dict[str, Any]) -> str | None:
    """Absolute PDF URL from a search result's `downloads` field, if any."""
    for d in result.get("downloads") or []:
        links = d.get("links") or {}
        href = links.get("pdf") or (
            links.get("original") if d.get("mimetype") == "application/pdf" else None
        )
        if href:
            return href if href.startswith("http") else f"{BASE_URL}{href}"
    return None


def parse_record(result: dict[str, Any]) -> dict[str, Any]:
    """Flatten one NTRS search result into a catalog row."""
    authors = [
        a["meta"]["author"]["name"]
        for a in sorted(result.get("authorAffiliations") or [], key=lambda a: a.get("sequence", 0))
        if a.get("meta", {}).get("author", {}).get("name")
    ]
    dates = [p.get("publicationDate") for p in result.get("publications") or []]
    dates += [result.get("distributionDate"), result.get("created")]
    year = next((int(d[:4]) for d in dates if d and d[:4].isdigit()), None)
    return {
        "id": str(result["id"]),
        "title": " ".join((result.get("title") or "").split()),
        "authors": "; ".join(authors),
        "year": year,
        "url": f"{BASE_URL}/citations/{result['id']}",
        "pdf_url": pdf_link(result) or "",
    }


def search(client: httpx.Client, query: str, size: int) -> list[dict[str, Any]]:
    resp = request_with_retries(client, "GET", SEARCH_URL, params={"q": query, "page.size": size})
    return resp.json().get("results", [])


def download_pdf(
    client: httpx.Client, url: str, dest: Path, max_mb: float, retries: int = 3
) -> bool:
    """Stream a PDF to `dest`, retrying network errors / 5xx with backoff."""
    if dest.exists() and dest.stat().st_size > 0:
        log.info("Skip (exists) %s", dest.name)
        return True
    tmp = dest.with_suffix(".part")
    for attempt in range(retries + 1):
        try:
            with client.stream("GET", url, follow_redirects=True) as resp:
                if resp.status_code < 500 and resp.status_code != 429:
                    resp.raise_for_status()
                    size = int(resp.headers.get("content-length") or 0)
                    if size > max_mb * 1024 * 1024:
                        log.warning("Skip %s: %.1f MB > --max-mb", dest.name, size / 2**20)
                        return False
                    with tmp.open("wb") as fh:
                        for chunk in resp.iter_bytes():
                            fh.write(chunk)
                    tmp.replace(dest)
                    log.info("Downloaded %s (%.1f MB)", dest.name, dest.stat().st_size / 2**20)
                    return True
                log.warning("HTTP %s for %s", resp.status_code, url)
        except httpx.HTTPStatusError as exc:  # 4xx: not retryable
            log.warning("Failed to download %s: %s", url, exc)
            return False
        except (httpx.HTTPError, OSError) as exc:
            log.warning("Error downloading %s: %s", dest.name, exc)
        tmp.unlink(missing_ok=True)
        if attempt < retries:
            time.sleep(2**attempt)
    log.warning("Giving up on %s", url)
    return False


RELEVANT = re.compile(
    r"flame|fire|combust|smoke|flammab|burn|droplet|soot|ignit|extinguish|spacecraft|"
    r"microgravity|reduced.gravity|saffire|bass|flex|acme|same",
    re.I,
)


OFF_TOPIC = re.compile(r"atmospher|troposph|stratosph|lidar|laser radar|modis|viirs", re.I)


def is_relevant(title: str) -> bool:
    """Drop off-topic hits (e.g. atmospheric aerosol or lidar papers for smoke queries)."""
    return bool(RELEVANT.search(title)) and not OFF_TOPIC.search(title)


def read_catalog(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        return {r["id"]: r for r in csv.DictReader(fh)}


def write_catalog(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CATALOG_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--queries", type=Path, default=QUERIES_FILE)
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    parser.add_argument("--max-per-query", type=int, default=15)
    parser.add_argument("--max-total", type=int, default=40, help="new records per run")
    parser.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    parser.add_argument("--max-mb", type=float, default=60, help="skip larger PDFs")
    parser.add_argument("--no-pdf", action="store_true", help="only write the catalog")
    parser.add_argument("--fresh", action="store_true", help="ignore the existing catalog.csv")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Merge with the existing catalog so re-running never drops documents already indexed.
    records: dict[str, dict[str, Any]] = (
        {} if args.fresh else read_catalog(args.out / "catalog.csv")
    )
    args.max_total += len(records)
    headers = {"User-Agent": "hestia-space-apps-2026/0.1 (research prototype)"}
    with httpx.Client(timeout=60, headers=headers) as client:
        for query in read_queries(args.queries):
            if len(records) >= args.max_total:
                break
            results = search(client, query, args.max_per_query)
            new = 0
            for r in results:
                rec = parse_record(r)
                if not is_relevant(rec["title"]):
                    continue
                if rec["id"] not in records and len(records) < args.max_total:
                    records[rec["id"]] = rec
                    new += 1
            log.info("%-55s %2d results, %2d new", query[:55], len(results), new)
            time.sleep(args.delay)

        rows = list(records.values())
        write_catalog(rows, args.out / "catalog.csv")
        log.info("Wrote %s (%d records)", args.out / "catalog.csv", len(rows))

        if args.no_pdf:
            return
        pdf_dir = args.out / "pdf"
        pdf_dir.mkdir(parents=True, exist_ok=True)
        ok = 0
        for rec in rows:
            if not rec["pdf_url"]:
                continue
            if download_pdf(client, rec["pdf_url"], pdf_dir / f"{rec['id']}.pdf", args.max_mb):
                ok += 1
            time.sleep(args.delay)
        no_pdf = sum(1 for r in rows if not r["pdf_url"])
        log.info("PDFs available: %d / %d records (%d without PDF)", ok, len(rows), no_pdf)


if __name__ == "__main__":
    main()
