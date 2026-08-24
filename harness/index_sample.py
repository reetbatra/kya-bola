"""Index shards by district first, then fetch audio only where it is needed.

The earlier sampler walked shards in order and read from the head of each,
which meant discovering districts by luck: Hindi has 193 shards and reached 14
districts of roughly a hundred before its budget ran out.

Reading a shard's district column without the audio attached runs about
thirteen times faster (2,387 rows/min against 179), because audio bytes
dominate every row. So build the index first, then spend the expensive audio
reads only on shards that hold districts still under quota, poorest district
first.
"""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from pathlib import Path

from datasets import Audio, load_dataset

from harness.languages import get as get_language
from harness.sample import DATASET, _to_wav, clip_id, list_shards


def build_index(
    language: str, token: str, peek_rows: int = 300
) -> dict[str, list[int]]:
    """Map district -> shard indices that contain it."""
    shards = list_shards(language, token)
    index: dict[str, list[int]] = defaultdict(list)
    for position, shard in enumerate(shards):
        try:
            stream = load_dataset(
                "parquet",
                data_files=f"hf://datasets/{DATASET}/{shard}",
                split="train",
                streaming=True,
                columns=["district"],
                token=token,
            )
            seen_here: set[str] = set()
            for row_number, row in enumerate(stream):
                if row_number >= peek_rows:
                    break
                seen_here.add((row.get("district") or "Unknown").strip())
            for district in seen_here:
                index[district].append(position)
        except Exception as exc:  # noqa: BLE001
            print(f"    ! index shard {position}: {type(exc).__name__}", flush=True)
    return dict(index), shards


def sample(
    language: str,
    out_dir: Path,
    manifest_path: Path,
    per_cell: int = 20,
    token: str | None = None,
) -> list[dict]:
    token = token or os.environ["HF_TOKEN"]
    meta = get_language(language)

    seen: set[str] = set()
    for path in sorted(out_dir.glob("manifest*.jsonl")):
        with path.open() as fh:
            for line in fh:
                if line.strip():
                    seen.add(json.loads(line)["clip_id"])

    index, shards = build_index(language, token)
    print(f"  {language}: {len(index)} districts across {len(shards)} shards", flush=True)

    have: Counter[str] = Counter()
    order: Counter[str] = Counter()
    for path in sorted(out_dir.glob("manifest*.jsonl")):
        with path.open() as fh:
            for line in fh:
                if not line.strip():
                    continue
                row = json.loads(line)
                if row["language"] == language:
                    have[row["district"]] += 1
                    order[row["district"]] += 1

    # Visit shards that serve the districts furthest from quota first, so an
    # interrupted run still spread its budget over the country.
    def shard_value(position: int) -> int:
        return sum(
            max(0, per_cell - have[district])
            for district, positions in index.items()
            if position in positions
        )

    rows: list[dict] = []
    with manifest_path.open("a") as manifest:
        for position in sorted(range(len(shards)), key=shard_value, reverse=True):
            if shard_value(position) == 0:
                break
            try:
                stream = load_dataset(
                    "parquet",
                    data_files=f"hf://datasets/{DATASET}/{shards[position]}",
                    split="train",
                    streaming=True,
                    token=token,
                ).cast_column("audio", Audio(decode=False))
            except Exception as exc:  # noqa: BLE001
                print(f"    ! shard {position}: {type(exc).__name__}", flush=True)
                continue

            for row in stream:
                district = (row.get("district") or "Unknown").strip()
                if have[district] >= per_cell:
                    continue
                transcript = (row.get("transcript") or "").strip()
                if not transcript:
                    continue

                cid = clip_id(language, district, order[district])
                order[district] += 1
                if cid in seen:
                    have[district] += 1
                    continue

                wav = out_dir / "clips" / language / district / f"{cid}.wav"
                try:
                    duration = _to_wav(row["audio"], wav)
                except Exception:  # noqa: BLE001
                    continue

                record = {
                    "clip_id": cid,
                    "language": language,
                    "sarvam_code": meta.request_code,
                    "sarvam_supported": meta.supported,
                    "state": (row.get("state") or "Unknown").strip(),
                    "district": district,
                    "transcript": transcript,
                    "duration_s": round(duration, 3),
                    "wav": str(wav.relative_to(out_dir)),
                }
                manifest.write(json.dumps(record, ensure_ascii=False) + "\n")
                manifest.flush()
                rows.append(record)
                have[district] += 1

                if shard_value(position) == 0:
                    break

    filled = sum(1 for d in index if have[d] >= per_cell)
    print(
        f"  {language}: +{len(rows)} clips | {len(have)} districts touched, "
        f"{filled}/{len(index)} at quota",
        flush=True,
    )
    return rows
