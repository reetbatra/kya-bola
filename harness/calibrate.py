"""Reproduce the published Vaani Benchmark numbers to validate this harness.

The Vaani team benchmarked 21 ASR systems on `Vaani-Benchmark-V1.0` (5,050
Hindi segments, 104 districts, three independent human transcriptions each) in
arXiv 2606.21408. For Sarvam Saaras v3 they report:

    Approach 1   20.3     WER against each reference set, then averaged
    Approach 2   16.9     best of the three references per utterance
    Approach 3   13.7     alignment across all three references
    District     18.3 +/- 4.6

If this harness lands near those figures on the same clips and the same model,
every later number in the project inherits that credibility. If it does not,
something here is wrong and needs finding before spending on 63 more languages.

Approach 3 is not reproduced: the paper describes it only as "alignment across
references" without enough detail to reimplement faithfully, and guessing at it
would produce a number that agrees or disagrees for unknown reasons.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import statistics
from collections import Counter
from pathlib import Path

import numpy as np
import soundfile as sf
from datasets import Audio, load_dataset

from harness.annotations import clean_reference
from harness.score import aggregate, score_clip

DATASET = "ARTPARK-IISc/Vaani-Benchmark-V1.0"
REFERENCE_FIELDS = ("transcription_v1", "transcription_v2", "transcription_v3")

# Published figures for Sarvam Saaras v3, arXiv 2606.21408 Table 2.
PUBLISHED = {
    "approach_1": 0.203,
    "approach_2": 0.169,
    "approach_3": 0.137,
    "district_mean": 0.183,
    "district_std": 0.046,
}


def sample(
    out_dir: Path,
    manifest_path: Path,
    per_district: int = 4,
    max_scan: int = 3000,
    seed: int = 20260824,
    shuffle_buffer: int = 300,
) -> list[dict]:
    """Pull a district-spread sample of the benchmark set."""
    token = os.environ["HF_TOKEN"]
    seen: set[str] = set()
    if manifest_path.exists():
        with manifest_path.open() as fh:
            seen = {json.loads(line)["clip_id"] for line in fh if line.strip()}

    stream = (
        load_dataset(DATASET, "Hindi", split="test", streaming=True, token=token)
        .cast_column("audio", Audio(decode=False))
        .shuffle(seed=seed, buffer_size=shuffle_buffer)
    )

    counts: Counter[str] = Counter()
    rows: list[dict] = []
    with manifest_path.open("a") as manifest:
        for index, row in enumerate(stream):
            if index >= max_scan:
                break
            district = (row.get("district") or "Unknown").strip()
            if counts[district] >= per_district:
                continue
            counts[district] += 1

            clip_id = f"bench-{index:06d}"
            if clip_id in seen:
                continue

            wav = out_dir / "bench_clips" / district / f"{clip_id}.wav"
            wav.parent.mkdir(parents=True, exist_ok=True)
            audio, sr = sf.read(io.BytesIO(row["audio"]["bytes"]), dtype="float32")
            sf.write(wav, np.asarray(audio, dtype=np.float32), sr, subtype="PCM_16")

            record = {
                "clip_id": clip_id,
                "language": "Hindi",
                "state": (row.get("state") or "Unknown").strip(),
                "district": district,
                "duration_s": float(row.get("duration") or 0.0),
                "wav": str(wav.relative_to(out_dir)),
                **{field: row.get(field) or "" for field in REFERENCE_FIELDS},
                # score_clip reads `transcript`; v1 is the default reference.
                "transcript": row.get(REFERENCE_FIELDS[0]) or "",
            }
            manifest.write(json.dumps(record, ensure_ascii=False) + "\n")
            manifest.flush()
            rows.append(record)

    print(f"sampled {len(rows)} clips across {len(counts)} districts")
    return rows


def _weighted_wer(scores) -> float | None:
    total = sum(s.ref_words for s in scores if s.wer is not None)
    if not total:
        return None
    return sum(s.wer * s.ref_words for s in scores if s.wer is not None) / total


def evaluate(manifest: list[dict], transcripts: dict[str, dict], provider: str) -> dict:
    """Score against all three reference sets and report both approaches."""
    per_reference = {}
    for field in REFERENCE_FIELDS:
        scores = []
        for clip in manifest:
            row = transcripts.get(clip["clip_id"]) or {}
            kind = row.get("failure_kind") or (None if row else "infrastructure")
            scores.append(
                score_clip({**clip, "transcript": clip[field]}, row.get("text"), provider, kind)
            )
        per_reference[field] = scores

    # Approach 1: cumulative WER against each reference set, then averaged.
    cumulative = {f: _weighted_wer(s) for f, s in per_reference.items()}
    usable = [v for v in cumulative.values() if v is not None]
    approach_1 = statistics.mean(usable) if usable else None

    # Approach 2: per utterance, take the reference the model matched best.
    best_scores = []
    for index, clip in enumerate(manifest):
        candidates = [
            per_reference[f][index]
            for f in REFERENCE_FIELDS
            if per_reference[f][index].wer is not None
        ]
        if candidates:
            best_scores.append(min(candidates, key=lambda s: s.wer))
    approach_2 = _weighted_wer(best_scores)

    # District mean and standard deviation, the shape the paper's last column
    # reports. Computed on approach 1's first reference set.
    per_district = aggregate(per_reference[REFERENCE_FIELDS[0]], by=("district",), min_clips=1)
    district_values = [a.wer for a in per_district if a.wer is not None]
    district_mean = statistics.mean(district_values) if len(district_values) > 1 else None
    district_std = statistics.stdev(district_values) if len(district_values) > 1 else None

    # How much the three human transcribers disagree with each other. The paper
    # puts this at 10-15% WER and it is the floor no model can beat.
    inter_annotator = _inter_annotator_wer(manifest)

    return {
        "provider": provider,
        "clips": len(manifest),
        "scored": sum(1 for s in per_reference[REFERENCE_FIELDS[0]] if s.excluded is None),
        "districts": len(per_district),
        "per_reference_wer": cumulative,
        "approach_1": approach_1,
        "approach_2": approach_2,
        "district_mean": district_mean,
        "district_std": district_std,
        "inter_annotator_wer": inter_annotator,
    }


def _inter_annotator_wer(manifest: list[dict]) -> float | None:
    """WER between reference v1 and v2, treating v1 as truth.

    This measures the ground truth against itself. It is the noise floor of the
    whole benchmark, and any model difference smaller than it is not real.
    """
    scores = []
    for clip in manifest:
        # Both sides need cleaning here. score_pair strips annotations from the
        # reference only, because a hypothesis is normally model output with no
        # markup in it. v2 is a human transcript and carries the same tags.
        scores.append(
            score_clip(
                {**clip, "transcript": clip[REFERENCE_FIELDS[0]]},
                clean_reference(clip[REFERENCE_FIELDS[1]]).text,
                "human-v2",
            )
        )
    return _weighted_wer(scores)


def report(result: dict) -> None:
    print(f"\n=== calibration: {result['provider']} ===")
    print(f"clips {result['scored']} of {result['clips']} across {result['districts']} districts\n")
    print(f"{'metric':<16}{'ours':>10}{'published':>12}{'delta':>10}")
    rows = [
        ("approach 1", result["approach_1"], PUBLISHED["approach_1"]),
        ("approach 2", result["approach_2"], PUBLISHED["approach_2"]),
        ("district mean", result["district_mean"], PUBLISHED["district_mean"]),
        ("district std", result["district_std"], PUBLISHED["district_std"]),
    ]
    for label, ours, published in rows:
        if ours is None:
            print(f"{label:<16}{'n/a':>10}{published:>11.1%}")
            continue
        delta = (ours - published) * 100
        print(f"{label:<16}{ours:>9.1%}{published:>11.1%}{delta:>+9.1f}pt")

    floor = result["inter_annotator_wer"]
    if floor is not None:
        print(f"\nhuman v1 vs v2 WER: {floor:.1%}  (paper reports 10-15%)")
        print("Nothing below this line distinguishes two models.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--manifest", type=Path, default=Path("data/bench_manifest.jsonl"))
    parser.add_argument("--cache", type=Path, default=Path("data/bench_transcripts.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("data/calibration.json"))
    parser.add_argument("--provider", default="sarvam:saaras:v3")
    parser.add_argument("--per-district", type=int, default=4)
    parser.add_argument("--max-scan", type=int, default=3000)
    parser.add_argument("--sample-only", action="store_true")
    args = parser.parse_args()

    if not args.manifest.exists():
        sample(args.data_dir, args.manifest, args.per_district, args.max_scan)
    if args.sample_only:
        return

    from harness.run import build_provider, load_manifest, transcribe_all

    manifest = load_manifest(args.manifest)
    provider = build_provider(args.provider)
    transcripts = transcribe_all(provider, manifest, args.data_dir, args.cache)
    result = evaluate(manifest, transcripts, provider.name)
    report(result)
    args.out.write_text(json.dumps(result, indent=1, ensure_ascii=False))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
