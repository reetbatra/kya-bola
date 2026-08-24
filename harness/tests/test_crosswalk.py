"""Tests for the Vaani -> geoBoundaries district join.

These run against the real boundary files in data/, so they double as a guard
against someone swapping in a different boundary vintage without noticing that
districts stopped resolving.
"""

import json
from pathlib import Path

import pytest

from harness.crosswalk import ABSENT, DATA, build, fold, split_camel

pytestmark = pytest.mark.skipif(
    not (DATA / "ind_adm2_simplified.geojson").exists(),
    reason="boundary files not downloaded; run scripts/fetch_boundaries.sh",
)


@pytest.fixture(scope="module")
def crosswalk():
    return build()


def test_every_vaani_district_is_accounted_for(crosswalk):
    total = sum(len(v) for v in crosswalk.values())
    assert total == 165, "all 165 Vaani districts must appear in exactly one bucket"


def test_no_district_silently_disappears(crosswalk):
    """Unmatched districts must carry a reason. A hole in the map is a lie."""
    for record in crosswalk["unmatched"]:
        assert record["shape_ids"] == []
        assert record.get("reason"), f"{record['district']} has no documented reason"


def test_only_known_districts_are_unmatched(crosswalk):
    got = {(r["state"], r["district"]) for r in crosswalk["unmatched"]}
    assert got == set(ABSENT), (
        "the set of unmappable districts changed; if a boundary file was "
        "swapped, review the join before trusting the map"
    )


def test_coverage_is_at_least_ninety_seven_percent(crosswalk):
    mapped = len(crosswalk["matched"]) + len(crosswalk["review"])
    assert mapped / 165 >= 0.97


def test_nothing_is_left_to_fuzzy_guessing(crosswalk):
    """Every match should be exact, manual or composite after review."""
    assert crosswalk["review"] == [], (
        "fuzzy matches present: "
        + ", ".join(f"{r['district']}->{r['matched_name']}" for r in crosswalk["review"])
    )


def test_shape_ids_are_unique_across_districts(crosswalk):
    """Two Vaani districts must never claim the same polygon."""
    seen: dict[str, str] = {}
    for record in crosswalk["matched"]:
        for shape_id in record["shape_ids"]:
            assert shape_id not in seen, (
                f"{record['district']} and {seen[shape_id]} both map to {shape_id}"
            )
            seen[shape_id] = record["district"]


def test_state_scoping_separates_duplicate_names(crosswalk):
    """Aurangabad exists in both Bihar and Maharashtra."""
    by_name: dict[str, list[dict]] = {}
    for record in crosswalk["matched"]:
        by_name.setdefault(record["district"], []).append(record)
    for name, records in by_name.items():
        if len(records) > 1:
            states = {r["state"] for r in records}
            assert len(states) == len(records), f"{name} resolved ambiguously"


def test_composite_district_gets_both_polygons(crosswalk):
    goa = next(r for r in crosswalk["matched"] if r["district"] == "NorthSouthGoa")
    assert len(goa["shape_ids"]) == 2


def test_split_camel():
    assert split_camel("KamrupMetropolitan") == "Kamrup Metropolitan"
    assert split_camel("North24Parganas") == "North24 Parganas"
    assert split_camel("Chittoor") == "Chittoor"


def test_fold_is_diacritic_and_punctuation_insensitive():
    assert fold("Mahārāshtra") == fold("Maharashtra")
    assert fold("Kaimur (Bhabua)") == "kaimurbhabua"
    assert fold("The Nilgiris District") == "thenilgiris"


def test_crosswalk_file_on_disk_matches_build(crosswalk):
    path = DATA / "district_crosswalk.json"
    if not path.exists():
        pytest.skip("crosswalk not generated yet")
    on_disk = json.loads(path.read_text())
    assert len(on_disk["matched"]) == len(crosswalk["matched"])
    assert len(on_disk["unmatched"]) == len(crosswalk["unmatched"])
