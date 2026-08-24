"""The results JSON is a contract between the Python harness and the site.

The site reads these files at build time with hand-written TypeScript types.
Nothing else checks that the two agree, so a renamed field would surface as a
blank map rather than an error. These tests pin the field names that
web/src/lib/types.ts declares.
"""

import json
import re
from pathlib import Path

import pytest

from harness.run import summarize
from harness.score import aggregate, score_clip

ROOT = Path(__file__).resolve().parent.parent.parent
TYPES = ROOT / "web" / "src" / "lib" / "types.ts"


def _clip(cid, lang="Hindi", district="D1"):
    return {
        "clip_id": cid, "language": lang, "district": district,
        "state": "S", "transcript": "एक दो तीन",
    }


@pytest.fixture
def summary():
    scores = [
        score_clip(_clip("a"), "एक दो तीन", "p"),
        score_clip(_clip("b", district="D2"), "एक दो चार", "p"),
    ]
    return summarize(scores, "p")


def _declared_fields(type_name: str) -> set[str]:
    if not TYPES.exists():
        pytest.skip("web/src/lib/types.ts not present")
    text = TYPES.read_text()
    match = re.search(rf"export type {type_name} = {{(.*?)}};", text, re.S)
    if not match:
        pytest.skip(f"{type_name} not found in types.ts")
    return set(re.findall(r"^\s*(\w+)\s*[?]?\s*:", match.group(1), re.M))


def test_provider_run_fields_match_typescript(summary):
    declared = _declared_fields("ProviderRun")
    missing = declared - set(summary)
    assert not missing, f"site expects fields the harness does not emit: {missing}"


def test_aggregate_fields_match_typescript():
    agg = aggregate([score_clip(_clip("a"), "एक दो तीन", "p")], min_clips=1)[0].as_dict()
    declared = _declared_fields("Aggregate")
    missing = declared - set(agg)
    assert not missing, f"site expects aggregate fields the harness omits: {missing}"


def test_aggregate_key_is_json_serialisable_as_list():
    """The site indexes key[0] and key[1]. A tuple would not survive JSON."""
    agg = aggregate([score_clip(_clip("a"), "एक", "p")], by=("language", "district"), min_clips=1)[0]
    payload = json.loads(json.dumps(agg.as_dict()))
    assert isinstance(payload["key"], list)
    assert payload["key"] == ["Hindi", "D1"]


def test_summary_round_trips_through_json(summary):
    assert json.loads(json.dumps(summary)) == summary


def test_district_grain_is_present_for_the_map(summary):
    """The map joins on by_district and by_language_district."""
    assert summary["by_district"], "map has nothing to colour"
    assert summary["by_language_district"], "language filter has nothing to read"
