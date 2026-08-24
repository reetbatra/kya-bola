"""Sample by striding across parquet row groups.

Districts in this corpus are interleaved at row-group granularity, not grouped
into consecutive shards: Hindi's first shard alone spans districts from Aizawl
to Washim, but each row group within it holds roughly one district. Reading the
head of every shard therefore kept landing on the same handful of districts, no
matter how many shards were walked.

Row groups are individually addressable in parquet, so this reads a strided set
of them, offset differently per shard, and takes only what each district still
needs. One HTTP range request per row group instead of one per row.
"""

from __future__ import annotations

import io
import json
import os
from collections import Counter
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import soundfile as sf
from huggingface_hub import HfFileSystem

from harness.languages import get as get_language
from harness.sample import DATASET, TARGET_SR, clip_id, list_shards


def _write_wav(raw: bytes, path: Path) -> float:
    array, sr = sf.read(io.BytesIO(raw), dtype="float32", always_2d=False)
    array = np.asarray(array, dtype=np.float32)
    if array.ndim > 1:
        array = array.mean(axis=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, array, sr, subtype="PCM_16")
    return array.shape[0] / sr


def load_state(out_dir: Path, language: str) -> tuple[set[str], Counter]:
    seen: set[str] = set()
    have: Counter[str] = Counter()
    for path in sorted(out_dir.glob("manifest*.jsonl")):
        with path.open() as fh:
            for line in fh:
                if not line.strip():
                    continue
                row = json.loads(line)
                seen.add(row["clip_id"])
                if row["language"] == language:
                    have[row["district"]] += 1
    return seen, have


def sample(
    language: str,
    out_dir: Path,
    manifest_path: Path,
    per_cell: int = 20,
    groups_per_shard: int = 3,
    max_shards: int | None = None,
    token: str | None = None,
) -> list[dict]:
    token = token or os.environ["HF_TOKEN"]
    meta = get_language(language)
    fs = HfFileSystem(token=token)

    shards = list_shards(language, token)
    if max_shards:
        shards = shards[:max_shards]

    seen, have = load_state(out_dir, language)
    order = Counter(have)
    rows: list[dict] = []

    with manifest_path.open("a") as manifest:
        for shard_index, shard in enumerate(shards):
            try:
                with fs.open(f"datasets/{DATASET}/{shard}", "rb") as fh:
                    pf = pq.ParquetFile(fh)
                    total_groups = pf.metadata.num_row_groups
                    # Offset the stride by shard so different shards sample
                    # different regions of the file, which is where the
                    # different districts live.
                    picks = sorted(
                        {
                            (shard_index * 5 + step * max(1, total_groups // groups_per_shard))
                            % total_groups
                            for step in range(groups_per_shard)
                        }
                    )
                    for group in picks:
                        # Check the row group's districts before pulling audio.
                        # One row group is roughly one district and about 16 MB
                        # of audio, so skipping a full one is the single
                        # biggest saving available.
                        probe = pf.read_row_group(group, columns=["district"])
                        districts = set(probe.column("district").to_pylist())
                        if all(have[(d or "Unknown").strip()] >= per_cell for d in districts):
                            continue
                        table = pf.read_row_group(
                            group, columns=["district", "state", "transcript", "audio"]
                        ).to_pylist()
                        for record in table:
                            district = (record.get("district") or "Unknown").strip()
                            if have[district] >= per_cell:
                                continue
                            transcript = (record.get("transcript") or "").strip()
                            if not transcript:
                                continue
                            cid = clip_id(language, district, order[district])
                            order[district] += 1
                            if cid in seen:
                                have[district] += 1
                                continue
                            wav = out_dir / "clips" / language / district / f"{cid}.wav"
                            try:
                                duration = _write_wav(record["audio"]["bytes"], wav)
                            except Exception:  # noqa: BLE001
                                continue
                            row = {
                                "clip_id": cid,
                                "language": language,
                                "sarvam_code": meta.request_code,
                                "sarvam_supported": meta.supported,
                                "state": (record.get("state") or "Unknown").strip(),
                                "district": district,
                                "transcript": transcript,
                                "duration_s": round(duration, 3),
                                "wav": str(wav.relative_to(out_dir)),
                            }
                            manifest.write(json.dumps(row, ensure_ascii=False) + "\n")
                            manifest.flush()
                            rows.append(row)
                            seen.add(cid)
                            have[district] += 1
            except Exception as exc:  # noqa: BLE001
                print(f"    ! {language} shard {shard_index}: {type(exc).__name__}: {exc}", flush=True)
                continue

    print(
        f"  {language}: +{len(rows)} clips | {len(have)} districts total "
        f"({sum(1 for v in have.values() if v >= per_cell)} at quota) "
        f"from {len(shards)} shards",
        flush=True,
    )
    return rows
