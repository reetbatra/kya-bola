"""Map Vaani district names onto geoBoundaries ADM2 polygons.

This is the join that decides whether the map has holes in it.

Two problems make it non-trivial:

1. geoBoundaries' IND ADM2 file carries only `shapeName` -- `shapeISO` is empty,
   so there is no LGD code to join on and no state column either. We derive each
   polygon's state by point-in-polygon against the ADM1 layer.
2. Vaani writes districts as CamelCase with no spaces ("KamrupMetropolitan",
   "NorthSouthGoa") and both sources spell Indian place names inconsistently
   (Anantpur/Anantapur, Bangalore/Bengaluru, Allahabad/Prayagraj).

Matching is state-scoped: a district name is only ever compared against
polygons inside the same state, which is what keeps the several Aurangabads,
Hamirpurs and Bilaspurs apart.
"""

from __future__ import annotations

import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

from shapely.geometry import shape

DATA = Path(__file__).resolve().parent.parent / "data"

# Vaani spelling -> geoBoundaries spelling, for cases no string metric should
# be trusted to guess. Every entry here was checked by hand against the
# polygon list; see `python -m harness.crosswalk` output.
MANUAL: dict[tuple[str, str], str] = {
    ("Karnataka", "Bangalore"): "Bengaluru Urban",
    ("Karnataka", "BangaloreRural"): "Bengaluru Rural",
    ("UttarPradesh", "Allahabad"): "Prayagraj",
    ("UttarPradesh", "Faizabad"): "Ayodhya",
    ("Maharashtra", "Bombay"): "Mumbai",
    ("Odisha", "Keonjhar"): "Kendujhar",
    ("Kerala", "Trivandrum"): "Thiruvananthapuram",
    # Transliteration differences, not different places.
    ("AndhraPradesh", "Vishakapattanam"): "Visakhapatnam",
    ("Chhattisgarh", "Kabirdham"): "Kabeerdham",
    ("Chhattisgarh", "Sarguja"): "Surguja",
    ("TamilNadu", "Nilgiris"): "The Nilgiris",
    ("Tripura", "Unakoti"): "Unokoti",
    ("WestBengal", "CoochBehar"): "Koch Bihar",
    ("WestBengal", "Darjeeling"): "Darjiling",
    ("WestBengal", "North24Parganas"): "North Twenty Four Parganas",
    # Hindi/Bengali direction words: Purba = East, Pashchim = West.
    ("Bihar", "EastChamparan"): "Purba Champaran",
    ("Bihar", "WestChamparan"): "Pashchim Champaran",
    # Sikkim renamed its four compass districts in 2021-22; the boundary file
    # still carries the old names. Gangtok is the former East District.
    ("Sikkim", "Gangtok"): "East District",
    # Reviewed by hand after the fuzzy matcher proposed them. Encoded here so
    # the crosswalk is a reviewed decision rather than a similarity threshold.
    ("Bihar", "Jahanabad"): "Jehanabad",
    ("Jharkhand", "Sahebganj"): "Sahibganj",
    ("Gujarat", "DevbhoomiDwarka"): "Devbhumi Dwarka",
    ("UttarPradesh", "Shamli"): "Samli",
    ("TamilNadu", "Kanyakumari"): "Kanniyakumari",
    ("Maharashtra", "Gondia"): "Gondiya",
    ("Bihar", "Kaimur"): "Kaimur (Bhabua)",
    ("WestBengal", "Malda"): "Maldah",
    ("WestBengal", "Purulia"): "Puruliya",
    ("AndhraPradesh", "Anantpur"): "Anantapur",
    ("Telangana", "Hyderabad"): "Hydrabad",
    # geoBoundaries splits Karbi Anglong into East and West polygons. West Karbi
    # Anglong became its own district in 2016; Vaani's plain "KarbiAnglong" is
    # the parent district, which is the East polygon here.
    ("Assam", "KarbiAnglong"): "Karbi Anglong East",
}

# Districts with real Vaani audio but no polygon in the 2021 boundary vintage.
# These are excluded from the map and named explicitly on the site rather than
# silently dropped or folded into a parent district, which would double-count
# against a parent that Vaani also samples separately.
ABSENT: dict[tuple[str, str], str] = {
    ("Haryana", "CharkhiDadri"):
        "created 2016 from Bhiwani; absent from the 2021 ADM2 release",
    ("AndhraPradesh", "Annamaya"):
        "created 2022 from Kadapa/Chittoor/Nellore; postdates the boundary file",
    ("AndhraPradesh", "Manyam"):
        "Parvathipuram Manyam, created 2022 from Vizianagaram/Srikakulam",
    ("AndhraPradesh", "SriSatyaSai"):
        "Sri Sathya Sai, created 2022 from Anantapur",
}

# Vaani groups these into one config; they are separate ADM2 polygons.
COMPOSITE: dict[tuple[str, str], list[str]] = {
    ("Goa", "NorthSouthGoa"): ["North Goa", "South Goa"],
}

_NOISE = re.compile(r"\b(district|dist|zilla|zila)\b")
_NONWORD = re.compile(r"[^a-z0-9]+")


def fold(text: str) -> str:
    """Diacritic-insensitive, punctuation-insensitive comparison key."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = _NOISE.sub(" ", text)
    return _NONWORD.sub("", text)


def split_camel(name: str) -> str:
    """"KamrupMetropolitan" -> "Kamrup Metropolitan"."""
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name)


def load_polygons() -> list[dict]:
    """ADM2 features, each tagged with the state it falls inside."""
    adm1 = json.loads((DATA / "ind_adm1_simplified.geojson").read_text())
    adm2 = json.loads((DATA / "ind_adm2_simplified.geojson").read_text())

    states = [
        (f["properties"]["shapeName"], shape(f["geometry"]))
        for f in adm1["features"]
    ]

    out = []
    for feature in adm2["features"]:
        geom = shape(feature["geometry"])
        point = geom.representative_point()
        state = next((name for name, poly in states if poly.contains(point)), None)
        if state is None:
            # Coastal or boundary slivers can miss every state polygon; fall
            # back to nearest rather than dropping the district.
            state = min(states, key=lambda s: s[1].distance(point))[0]
        out.append(
            {
                "shape_id": feature["properties"]["shapeID"],
                "name": feature["properties"]["shapeName"],
                "state": state,
                "key": fold(feature["properties"]["shapeName"]),
                "state_key": fold(state),
            }
        )
    return out


def _best(candidates: list[dict], target: str) -> tuple[dict | None, float]:
    best, score = None, 0.0
    for cand in candidates:
        ratio = SequenceMatcher(None, cand["key"], target).ratio()
        # Containment counts: "Kamrup" vs "Kamrup Metropolitan".
        if cand["key"].startswith(target) or target.startswith(cand["key"]):
            ratio = max(ratio, 0.93)
        if ratio > score:
            best, score = cand, ratio
    return best, score


def build(threshold: float = 0.86) -> dict:
    vaani = json.loads((DATA / "vaani_districts.json").read_text())
    polygons = load_polygons()

    by_state: dict[str, list[dict]] = {}
    for poly in polygons:
        by_state.setdefault(poly["state_key"], []).append(poly)

    matched, review, unmatched = [], [], []

    for entry in vaani:
        state, district = entry["state"], entry["district"]
        target = fold(split_camel(district))
        state_key = fold(state)
        candidates = by_state.get(state_key, [])

        if not candidates:  # state name itself did not line up
            best_state, best_ratio = None, 0.0
            for key in by_state:
                ratio = SequenceMatcher(None, key, state_key).ratio()
                if ratio > best_ratio:
                    best_state, best_ratio = key, ratio
            if best_ratio > 0.8 and best_state:
                candidates = by_state[best_state]

        record = {"config": entry["config"], "state": state, "district": district}

        if (state, district) in ABSENT:
            record |= {
                "shape_ids": [], "method": "absent", "score": 0.0,
                "reason": ABSENT[(state, district)],
            }
            unmatched.append(record)
            continue

        if (state, district) in COMPOSITE:
            names = {fold(n) for n in COMPOSITE[(state, district)]}
            ids = [c["shape_id"] for c in candidates if c["key"] in names]
            record |= {"shape_ids": ids, "method": "composite", "score": 1.0}
            (matched if ids else unmatched).append(record)
            continue

        if (state, district) in MANUAL:
            wanted = fold(MANUAL[(state, district)])
            hit = next((c for c in candidates if c["key"] == wanted), None)
            if hit:
                record |= {
                    "shape_ids": [hit["shape_id"]], "matched_name": hit["name"],
                    "method": "manual", "score": 1.0,
                }
                matched.append(record)
                continue

        best, score = _best(candidates, target)
        if best and score >= 0.995:
            method = "exact"
        elif best and score >= threshold:
            method = "fuzzy"
        else:
            method = "none"

        record |= {
            "shape_ids": [best["shape_id"]] if best and method != "none" else [],
            "matched_name": best["name"] if best else None,
            "method": method,
            "score": round(score, 3),
        }
        if method == "exact":
            matched.append(record)
        elif method == "fuzzy":
            review.append(record)
        else:
            unmatched.append(record)

    return {"matched": matched, "review": review, "unmatched": unmatched}


def main() -> None:
    result = build()
    out = DATA / "district_crosswalk.json"
    out.write_text(json.dumps(result, indent=1, ensure_ascii=False))

    total = sum(len(v) for v in result.values())
    print(f"Vaani districts        : {total}")
    print(f"  exact / manual match : {len(result['matched'])}")
    print(f"  fuzzy, needs review  : {len(result['review'])}")
    print(f"  UNMATCHED            : {len(result['unmatched'])}")

    if result["review"]:
        print("\nFuzzy matches to eyeball:")
        for r in sorted(result["review"], key=lambda r: r["score"]):
            print(f"  {r['score']:.3f}  {r['state']}/{r['district']:<24} -> {r['matched_name']}")
    if result["unmatched"]:
        print("\nNo polygon found:")
        for r in result["unmatched"]:
            print(f"  {r['state']}/{r['district']:<24} best guess: {r.get('matched_name')} ({r.get('score')})")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
