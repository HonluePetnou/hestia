"""BASS, BASS-II and Saffire runs built from the cleaned PSI tables (no database)."""

from app.models import Outcome
from pipeline.psi_runs import _saffire_outcome, _thickness_mm, bass2_runs, bass_runs, saffire_runs


def test_thickness_parses_raw_text_when_clean_value_is_missing() -> None:
    assert _thickness_mm({"thickness_mm": "0.25"}) == 0.25
    assert _thickness_mm({"thickness_raw": "037 mm"}) == 0.37
    assert _thickness_mm({"thickness_raw": ".33 cm"}) == 3.3
    assert _thickness_mm({"thickness_raw": "thin"}) is None


def test_saffire_outcome_rules() -> None:
    assert _saffire_outcome({"burn_length_microgravity_raw": "~0"}) is Outcome.extinction
    assert _saffire_outcome({"spread_microgravity_raw": "1.8 cm/s"}) is Outcome.spread
    assert _saffire_outcome({"burn_length_microgravity_raw": "12 cm"}) is Outcome.spread
    assert _saffire_outcome({"spread_microgravity_raw": "n/a"}) is Outcome.unknown


def test_run_labels_are_unique_within_each_experiment() -> None:
    for runs in (bass_runs() + bass2_runs(), saffire_runs()):
        labels = [r["run_label"] for r in runs]
        assert labels and len(labels) == len(set(labels))
