"""Stratified sampling from the Vaani transcribed corpus.

Never downloads the corpus. It is 234 GB of parquet against 29 GB of free disk,
so every read is streamed and only the sampled clips are written out as 16 kHz
mono WAV.

Sampling is per (language, district) cell with a fixed seed, so a rerun selects
the identical clips and nobody gets billed twice for a different sample.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import requests
import soundfile as sf
from datasets import Audio, load_dataset

from harness.languages import config_name, get as get_language

DATASET = "ARTPARK-IISc/Vaani-transcription-part"
TARGET_SR = 16_000

# Sarvam works best at 16 kHz and the corpus is already recorded at it, but
# resample defensively rather than trusting the card.
DEFAULT_PER_CELL = 40
DEFAULT_MIN_CELL = 10


@dataclass
class SampleConfig:
    language: str
    per_cell: int = DEFAULT_PER_CELL
    min_cell: int = DEFAULT_MIN_CELL
    seed: int = 20260824
    #: Stop scanning a language after this many rows. Hindi alone has 636k rows;
    #: without a ceiling a single language would dominate the run.
    #: Total rows of audio to read for this language. Spread across every
    #: shard rather than spent on the first few: see per_shard_for().
    max_scan: int = 60_000
    #: Rows to read from the head of each shard. Leave as None to derive it
    #: from the shard count so that every shard is visited.
    per_shard: int | None = None
    #: Never read fewer than this from a shard, even for a config with hundreds.
    min_per_shard: int = 12


def shard_districts(shard: str, token: str, limit: int = 400) -> Counter[str]:
    """Districts present in the head of a shard, read WITHOUT the audio column.

    Parquet column pushdown makes this roughly thirteen times faster than
    scanning with audio attached (2,387 rows/min against 179), because the
    audio bytes dominate every row. Knowing which districts a shard holds means
    we can skip shards whose districts are already full instead of downloading
    50 rows of audio to discover they were useless.
    """
    stream = load_dataset(
        "parquet",
        data_files=f"hf://datasets/{DATASET}/{shard}",
        split="train",
        streaming=True,
        columns=["district"],
        token=token,
    )
    counts: Counter[str] = Counter()
    for index, row in enumerate(stream):
        if index >= limit:
            break
        counts[(row.get("district") or "Unknown").strip()] += 1
    return counts


def list_shards(language: str, token: str, split: str = "train") -> list[str]:
    """Every parquet shard for a language config, in repo order.

    Streaming a config sequentially reads shards in order and stops wherever the
    scan budget runs out, so it only ever sees the districts stored near the
    front of the file. Hindi has 250 shards; a sequential scan of 2,500 rows
    reached 15 districts out of roughly a hundred. Addressing shards explicitly
    is what makes district coverage a property of the sampler rather than an
    accident of where the budget ran out.
    """
    response = requests.get(
        "https://huggingface.co/api/datasets/"
        f"{DATASET}/tree/main/audio/{language}?recursive=true",
        headers={"Authorization": f"Bearer {token}"},
        timeout=90,
    )
    response.raise_for_status()
    return sorted(
        entry["path"]
        for entry in response.json()
        if entry.get("type") == "file"
        and entry["path"].endswith(".parquet")
        and f"/{split}-" in entry["path"]
    )


def per_shard_for(cfg: "SampleConfig", shard_count: int) -> int:
    """Rows to read from each shard so the budget covers all of them.

    Districts are grouped across consecutive shards, so a fixed per-shard read
    combined with a fixed total budget silently truncates wide configs: Hindi
    has 193 shards, and reading 40 rows from each exhausted a 4,000-row budget
    halfway through the file, reaching 14 districts out of roughly a hundred.
    Everything stored in the back half was invisible.

    Deriving the per-shard read from the shard count means the budget is spread
    over the whole config instead of spent on its opening.
    """
    if cfg.per_shard is not None:
        return cfg.per_shard
    return max(cfg.min_per_shard, cfg.max_scan // max(shard_count, 1))


def clip_id(language: str, district: str, index: int) -> str:
    raw = f"{language}/{district}/{index}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def _to_wav(audio: dict, path: Path) -> float:
    """Write an undecoded HF audio row to 16 kHz mono WAV. Returns duration.

    We take the raw bytes rather than letting `datasets` decode. Since v4 that
    path requires `torchcodec`, which drags in torch and couples us to a
    specific ffmpeg major version; soundfile reads these WAVs directly.
    """
    array, sr = sf.read(io.BytesIO(audio["bytes"]), dtype="float32", always_2d=False)
    array = np.asarray(array, dtype=np.float32)
    if array.ndim > 1:
        array = array.mean(axis=1)
    if sr != TARGET_SR:
        # Linear resample. The corpus is already 16 kHz, so this is a guard
        # rather than a hot path; if it ever fires on real data, revisit.
        duration = array.shape[0] / sr
        target_n = int(round(duration * TARGET_SR))
        array = np.interp(
            np.linspace(0, array.shape[0] - 1, target_n),
            np.arange(array.shape[0]),
            array,
        ).astype(np.float32)
        sr = TARGET_SR
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, array, sr, subtype="PCM_16")
    return array.shape[0] / sr


def sample_language(
    cfg: SampleConfig,
    out_dir: Path,
    token: str | None = None,
    manifest_path: Path | None = None,
) -> list[dict]:
    """Sample one language config into WAVs plus manifest rows.

    Rows already present in the manifest are skipped, so an interrupted run
    resumes instead of re-downloading.
    """
    language = get_language(cfg.language)
    token = token or os.environ.get("HF_TOKEN")
    if not token:
        raise RuntimeError(
            "HF_TOKEN is not set. Accept the dataset terms at "
            f"https://huggingface.co/datasets/{DATASET} and put a read token "
            "in .env as HF_TOKEN."
        )

    manifest_path = manifest_path or out_dir / "manifest.jsonl"
    seen: set[str] = set()
    if manifest_path.exists():
        with manifest_path.open() as fh:
            seen = {json.loads(line)["clip_id"] for line in fh if line.strip()}

    shards = list_shards(cfg.language, token)
    if not shards:
        raise RuntimeError(f"no train shards found for {cfg.language}")

    per_shard = per_shard_for(cfg, len(shards))
    # Every shard gets visited. The budget is the per-shard read times the
    # shard count, not a separate ceiling that can cut the walk short.
    budget = per_shard * len(shards)

    per_district: Counter[str] = Counter()
    order: Counter[str] = Counter()
    rows: list[dict] = []
    scanned = 0

    with manifest_path.open("a") as manifest:
        for shard_index, shard in enumerate(shards):
            if scanned >= budget:
                break
            # Peek at the shard's districts before paying for any audio.
            try:
                present = shard_districts(shard, token)
            except Exception as exc:  # noqa: BLE001
                print(f"  ! {cfg.language} shard {shard_index} peek: {type(exc).__name__}")
                present = None
            if present is not None and all(
                per_district[d] >= cfg.per_cell for d in present
            ):
                continue  # every district here is already full

            url = f"hf://datasets/{DATASET}/{shard}"
            try:
                stream = load_dataset(
                    "parquet", data_files=url, split="train",
                    streaming=True, token=token,
                ).cast_column("audio", Audio(decode=False))
            except Exception as exc:  # noqa: BLE001
                print(f"  ! {cfg.language} shard {shard_index}: {type(exc).__name__}: {exc}")
                continue

            # Count every row READ from this shard, not just the ones kept.
            # Counting only kept rows let a shard whose districts were already
            # full spin through thousands of rows while appearing to have taken
            # nothing, consuming the whole budget before the walk reached the
            # later shards.
            read_here = 0
            for row in stream:
                if read_here >= per_shard or scanned >= budget:
                    break
                read_here += 1
                scanned += 1

                district = (row.get("district") or "Unknown").strip()
                transcript = (row.get("transcript") or "").strip()
                if not transcript or per_district[district] >= cfg.per_cell:
                    continue

                index = order[district]
                order[district] += 1
                cid = clip_id(cfg.language, district, index)
                if cid in seen:
                    per_district[district] += 1
                    continue

                wav_path = out_dir / "clips" / cfg.language / district / f"{cid}.wav"
                try:
                    duration = _to_wav(row["audio"], wav_path)
                except Exception as exc:  # noqa: BLE001 - record and move on
                    print(f"  ! decode failed for {cid}: {type(exc).__name__}: {exc}")
                    continue

                record = {
                    "clip_id": cid,
                    "language": cfg.language,
                    "sarvam_code": language.request_code,
                    "sarvam_supported": language.supported,
                    "state": (row.get("state") or "Unknown").strip(),
                    "district": district,
                    "transcript": transcript,
                    "duration_s": round(duration, 3),
                    "wav": str(wav_path.relative_to(out_dir)),
                    "shard": shard_index,
                }
                manifest.write(json.dumps(record, ensure_ascii=False) + "\n")
                manifest.flush()
                rows.append(record)
                per_district[district] += 1

    thin = [d for d, n in per_district.items() if n < cfg.min_cell]
    if thin:
        print(
            f"  {cfg.language}: {len(thin)} district(s) under {cfg.min_cell} clips "
            f"-> flagged low-confidence, not dropped: {', '.join(sorted(thin)[:6])}"
            + (" ..." if len(thin) > 6 else "")
        )
    print(
        f"  {cfg.language}: {len(rows)} new clips across {len(per_district)} districts "
        f"from {len(shards)} shards ({per_shard}/shard, scanned {scanned:,} rows)"
    )
    return rows
