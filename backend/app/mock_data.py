"""Placeholder data used by the API when the database is empty or unreachable,
and inserted into the database by `pipeline.ingest --mock`.

EVERYTHING HERE IS FAKE. Experiment names/platforms are real NASA investigations,
but all numbers, findings and citations are invented placeholders marked "[MOCK]".
Do not present them as science.
"""

from app.models import Gravity, Outcome
from app.schemas import ExperimentDetail, FindingOut, SourceRef, TestRunOut

MOCK_DOCUMENTS = [
    {"ntrs_id": "MOCK-0001", "title": "[MOCK] Placeholder report on solid-fuel flame spread"},
    {"ntrs_id": "MOCK-0002", "title": "[MOCK] Placeholder report on droplet combustion"},
    {"ntrs_id": "MOCK-0003", "title": "[MOCK] Placeholder report on smoke detection"},
]


def mock_doc_url(ntrs_id: str) -> str:
    return f"https://ntrs.nasa.gov/citations/{ntrs_id}"


def _src(i: int, page: int) -> SourceRef:
    doc = MOCK_DOCUMENTS[i]
    return SourceRef(
        ntrs_id=doc["ntrs_id"], title=doc["title"], page=page, url=mock_doc_url(doc["ntrs_id"])
    )


def _run(label: str, fuel: str, o2: float, kpa: float, outcome: Outcome, **kw) -> TestRunOut:
    return TestRunOut(
        run_label=label,
        fuel=fuel,
        oxygen_percent=o2,
        pressure_kpa=kpa,
        outcome=outcome,
        gravity=kw.pop("gravity", Gravity.microgravity),
        **kw,
    )


_EXPERIMENTS: list[dict] = [
    {
        "code": "BASS",
        "name": "Burning and Suppression of Solids",
        "platform": "ISS (Microgravity Science Glovebox)",
        "description": "Burning of small solid fuel samples in microgravity.",
        "objectives": "[MOCK] Placeholder objectives.",
        "runs": [
            _run("BASS-M1", "PMMA", 21.0, 101.3, Outcome.spread, flow_velocity_cm_s=5.0),
            _run("BASS-M2", "cotton-fiberglass", 16.0, 101.3, Outcome.extinction),
        ],
        "findings": [
            ("[MOCK] Placeholder finding about concurrent-flow flame spread.", 0.8, 0.7, 0.6, 0, 4),
        ],
    },
    {
        "code": "SAFFIRE",
        "name": "Spacecraft Fire Safety Experiment",
        "platform": "Cygnus cargo vehicle",
        "description": "Large-scale fire experiments aboard an uncrewed Cygnus vehicle.",
        "objectives": "[MOCK] Placeholder objectives.",
        "runs": [
            _run("SAF-M1", "SIBAL cotton-fiberglass", 21.0, 101.3, Outcome.spread),
            _run("SAF-M2", "Nomex", 21.0, 101.3, Outcome.complete_burn),
        ],
        "findings": [
            ("[MOCK] Placeholder finding about large-sample fire growth.", 0.9, 0.9, 0.7, 0, 7),
        ],
    },
    {
        "code": "SAME",
        "name": "Smoke Aerosol Measurement Experiment",
        "platform": "ISS",
        "description": "Measures smoke particle properties from overheated spacecraft materials.",
        "objectives": "[MOCK] Placeholder objectives.",
        "runs": [_run("SAME-M1", "Teflon", 21.0, 101.3, Outcome.unknown)],
        "findings": [
            ("[MOCK] Placeholder finding about smoke detector sensitivity.", 0.6, 0.8, 0.5, 2, 2),
        ],
    },
    {
        "code": "FLEX",
        "name": "Flame Extinguishment Experiment",
        "platform": "ISS (Combustion Integrated Rack)",
        "description": "Isolated fuel-droplet combustion and extinction in microgravity.",
        "objectives": "[MOCK] Placeholder objectives.",
        "runs": [
            _run(
                "FLEX-M1",
                "n-heptane",
                21.0,
                101.3,
                Outcome.extinction,
                initial_diameter_mm=3.0,
                burn_rate_k=0.6,
            ),
            _run(
                "FLEX-M2",
                "methanol",
                30.0,
                101.3,
                Outcome.complete_burn,
                initial_diameter_mm=2.5,
                burn_rate_k=0.5,
            ),
        ],
        "findings": [
            ("[MOCK] Placeholder finding about cool-flame droplet burning.", 0.5, 0.6, 0.6, 1, 12),
        ],
    },
    {
        "code": "ACME",
        "name": "Advanced Combustion via Microgravity Experiments",
        "platform": "ISS (Combustion Integrated Rack)",
        "description": "A set of gaseous-flame investigations in microgravity.",
        "objectives": "[MOCK] Placeholder objectives.",
        "runs": [_run("ACME-M1", "ethylene", 21.0, 101.3, Outcome.unknown)],
        "findings": [],
    },
]


def experiments() -> list[ExperimentDetail]:
    """Return the mock experiments as API schemas."""
    out: list[ExperimentDetail] = []
    finding_id = 1
    for e in _EXPERIMENTS:
        findings = []
        for statement, moon, mars, conf, doc_i, page in e["findings"]:
            findings.append(
                FindingOut(
                    id=finding_id,
                    experiment_code=e["code"],
                    statement=statement,
                    relevance_moon=moon,
                    relevance_mars=mars,
                    confidence=conf,
                    sources=[_src(doc_i, page)],
                )
            )
            finding_id += 1
        out.append(
            ExperimentDetail(
                code=e["code"],
                name=e["name"],
                platform=e["platform"],
                description=e["description"],
                objectives=e["objectives"],
                test_runs=e["runs"],
                test_run_count=len(e["runs"]),
                findings=findings,
            )
        )
    return out
