"""Build the Flame-in-Freefall RAG corpus.

Inputs : docs/resources/*.md, docs/psi/batch*.json, docs/psi/annotations_curated.json
Outputs: out/investigations.json, out/investigations.csv, out/psi_md/*.md, out/chunks.jsonl

Usage: python3 scripts/build_corpus.py [--max-chars 1800]
"""
import argparse, csv, glob, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out")

SECTIONS = [  # (json key, heading)
    ("objectives", "Objectives"), ("approach", "Approach"), ("hypothesis", "Hypothesis"),
    ("impacts", "Research Impacts / Earth Benefits"), ("key_results_from_table", "Key results (from experimental table)"),
    ("notable_discovery", "Notable discovery"),
]


def load_investigations():
    recs = []
    for f in sorted(glob.glob(os.path.join(ROOT, "docs/psi/batch*.json"))):
        recs += json.load(open(f, encoding="utf-8"))
    ann = json.load(open(os.path.join(ROOT, "docs/psi/annotations_curated.json"), encoding="utf-8"))
    # Verbatim text from the official PSI pages replaces summarized fields.
    over = {}
    for f in sorted(glob.glob(os.path.join(ROOT, "docs/psi/verbatim_overrides*.json"))):
        over.update({k: v for k, v in json.load(open(f, encoding="utf-8")).items() if k.startswith("PSI-")})
    for r in recs:
        o = over.get(r["psi_id"], {})
        for k, v in o.items():
            if k == "publications":
                if v:
                    r["publications_partial"] = v
                    r["publications_count_on_page"] = len(v)
            elif k == "experimental_table_rows":
                et = r.setdefault("experimental_table", {}) or {}
                et["rows"] = v
                r["experimental_table"] = et
            else:
                r[k] = v
        r["verbatim"] = bool(o)
        a = ann.get(r["psi_id"], {})
        r["curated"] = {k: a.get(k) for k in ("tier", "pillars", "habitat_relevance", "cross_refs")}
    recs.sort(key=lambda r: (r["curated"]["tier"] or 9, int(r["psi_id"].split("-")[1])))
    return recs


def fmt(v):
    if isinstance(v, dict):
        return "; ".join(f"{k}: {fmt(x)}" for k, x in v.items())
    if isinstance(v, list):
        return ", ".join(fmt(x) for x in v)
    return "" if v is None else str(v)


def header(r):
    return (f"[{r['psi_id']} {r['acronym']}] {r['title']} | {r.get('project_type','')} | "
            f"fuel: {r.get('fuel_category','')} | hardware: {fmt(r.get('hardware'))}")


def investigation_md(r):
    c = r["curated"]
    lines = [
        "---",
        f"doc_id: {r['psi_id'].lower()}", f"psi_id: {r['psi_id']}", f"acronym: \"{r['acronym']}\"",
        f"title: \"{r['title']}\"", f"source_url: {r['url']}", f"doi: {r.get('doi','')}",
        "source_type: psi_investigation", "license: CC0-1.0 (PSI data)",
        f"curated_fire_safety_tier: {c['tier']}", f"curated_pillars: {c['pillars']}",
        "---", "", f"# {r['psi_id']} — {r['title']}", "",
        "## Metadata",
    ]
    for k in ("research_area", "sub_research_area", "project_type", "proposal_title", "platform", "start_date",
              "end_date", "dataset_size", "related", "hardware", "fuel_category", "fuels", "diluents", "key_conditions"):
        if r.get(k) not in (None, "", []):
            lines.append(f"- {k.replace('_',' ')}: {fmt(r[k])}")
    for key, h in SECTIONS:
        if r.get(key):
            lines += ["", f"## {h}", r[key]]
    if r.get("contacts"):
        lines += ["", "## Contacts", *[f"- {x}" for x in r["contacts"]]]
    et = r.get("experimental_table")
    if et:
        lines += ["", "## Experimental table (PSI)"]
        if et.get("rows") is not None:
            lines.append(f"- rows: {et['rows']}")
        if et.get("columns"):
            lines.append(f"- columns: {', '.join(et['columns'])}")
        for s in et.get("sample_rows", []):
            lines.append(f"- sample: {s}")
        if et.get("note"):
            lines.append(f"- note: {et['note']}")
    if r.get("data_folders"):
        lines += ["", "## Data folders in PSI", fmt(r["data_folders"])]
    if r.get("publications_partial"):
        n = r.get("publications_count_on_page")
        if n and n == len(r["publications_partial"]):
            lines += ["", f"## Publications (all {n} listed on PSI page)"]
        else:
            lines += ["", "## Selected publications" + (f" (partial list; {n} on PSI page)" if n else " (partial list)")]
        lines += [f"- {p}" for p in r["publications_partial"]]
    lines += ["", "## Curated annotation (not NASA text)",
              f"- fire-safety tier: {c['tier']}", f"- pillars: {fmt(c['pillars'])}",
              f"- habitat relevance: {c['habitat_relevance']}", f"- see also: {fmt(c['cross_refs'])}"]
    return "\n".join(lines) + "\n"


def split_text(text, max_chars):
    """Split on paragraph/sentence boundaries into pieces <= max_chars."""
    if len(text) <= max_chars:
        return [text]
    parts, cur = [], ""
    for sent in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(])", text):
        if len(cur) + len(sent) + 1 > max_chars and cur:
            parts.append(cur.strip()); cur = ""
        cur += sent + " "
    if cur.strip():
        parts.append(cur.strip())
    return parts


def investigation_chunks(r, max_chars):
    base = {"doc_id": r["psi_id"].lower(), "psi_id": r["psi_id"], "acronym": r["acronym"], "title": r["title"],
            "source_url": r["url"], "doi": r.get("doi"), "source_type": "psi_investigation",
            "project_type": r.get("project_type"), "fuel_category": r.get("fuel_category"),
            "hardware": r.get("hardware"), "start_date": r.get("start_date"), "end_date": r.get("end_date"),
            "fire_safety_tier": r["curated"]["tier"], "pillars": r["curated"]["pillars"]}
    h = header(r)
    out = []
    meta_txt = "; ".join(f"{k.replace('_',' ')}: {fmt(r[k])}" for k in
                         ("sub_research_area", "platform", "start_date", "end_date", "related", "fuels", "diluents", "key_conditions")
                         if r.get(k) not in (None, "", []))
    out.append(("overview", meta_txt + f"; curated habitat relevance: {r['curated']['habitat_relevance']}"))
    for key, name in SECTIONS:
        if r.get(key):
            for i, piece in enumerate(split_text(r[key], max_chars)):
                out.append((name.lower() + (f" ({i+1})" if i else ""), piece))
    et = r.get("experimental_table")
    if et:
        out.append(("experimental table", f"rows: {et.get('rows')}; columns: {fmt(et.get('columns'))}; samples: {' || '.join(et.get('sample_rows', []))}"))
    if r.get("publications_partial"):
        out.append(("publications", " || ".join(r["publications_partial"])))
    if r.get("contacts"):
        out.append(("contacts", "; ".join(r["contacts"])))
    return [dict(base, chunk_id=f"{base['doc_id']}#{i:02d}", section=s, text=f"{h}\nSection: {s}\n{t}")
            for i, (s, t) in enumerate(out)]


def parse_front_matter(md):
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", md, re.S)
    meta, body = {}, md
    if m:
        body = m.group(2)
        for line in m.group(1).splitlines():
            if ":" in line and not line.startswith(" "):
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip().strip('"')
    return meta, body


def resource_chunks(path, max_chars):
    meta, body = parse_front_matter(open(path, encoding="utf-8").read())
    doc_id = meta.get("doc_id", os.path.basename(path))
    title = meta.get("title", doc_id)
    base = {"doc_id": doc_id, "title": title, "source_url": meta.get("source_url") or meta.get("source_urls"),
            "source_type": meta.get("source_type"), "tags": meta.get("tags")}
    chunks, section, buf = [], "intro", []

    def flush():
        txt = "\n".join(buf).strip()
        if txt:
            for i, piece in enumerate(split_text(txt, max_chars)):
                chunks.append((section + (f" ({i+1})" if i else ""), piece))

    for line in body.splitlines():
        if re.match(r"^#{1,3} ", line):
            flush(); buf = []; section = line.lstrip("#").strip()
        else:
            buf.append(line)
    flush()
    return [dict(base, chunk_id=f"{doc_id}#{i:02d}", section=s, text=f"[{title}]\nSection: {s}\n{t}")
            for i, (s, t) in enumerate(chunks)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-chars", type=int, default=1800)
    a = ap.parse_args()
    os.makedirs(os.path.join(OUT, "psi_md"), exist_ok=True)

    recs = load_investigations()
    json.dump(recs, open(os.path.join(OUT, "investigations.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)

    cols = ["psi_id", "acronym", "title", "tier", "pillars", "project_type", "platform", "start_date", "end_date",
            "fuel_category", "fuels", "hardware", "key_conditions", "dataset_size", "doi", "url", "habitat_relevance"]
    with open(os.path.join(OUT, "investigations.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in recs:
            row = {k: fmt(r.get(k)) for k in cols}
            row.update(tier=r["curated"]["tier"], pillars=fmt(r["curated"]["pillars"]),
                       habitat_relevance=r["curated"]["habitat_relevance"])
            w.writerow(row)

    chunks = []
    for r in recs:
        open(os.path.join(OUT, "psi_md", f"{r['psi_id']}_{re.sub(r'[^A-Za-z0-9]+','-',r['acronym']).strip('-')}.md"),
             "w", encoding="utf-8").write(investigation_md(r))
        chunks += investigation_chunks(r, a.max_chars)
    for p in sorted(glob.glob(os.path.join(ROOT, "docs/resources/*.md"))):
        chunks += resource_chunks(p, a.max_chars)

    with open(os.path.join(OUT, "chunks.jsonl"), "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"{len(recs)} investigations, {len(chunks)} chunks -> {OUT}")


if __name__ == "__main__":
    main()
