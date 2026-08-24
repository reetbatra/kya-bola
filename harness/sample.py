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
    max_scan: int = 60_000
    shuffle_buffer: int = 10_000


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

    stream = load_dataset(
        DATASET,
        config_name(cfg.language),
        split="train",
        streaming=True,
        token=token,
    ).cast_column("audio", Audio(decode=False)).shuffle(
        seed=cfg.seed, buffer_size=cfg.shuffle_buffer
    )

    per_district: Counter[str] = Counter()
    order: Counter[str] = Counter()
    rows: list[dict] = []
    scanned = 0
    district_arrival: list[str] = []

    with manifest_path.open("a") as manifest:
        for row in stream:
            scanned += 1
            if scanned > cfg.max_scan:
                break

            district = (row.get("district") or "Unknown").strip()
            if len(district_arrival) < 2_000:
                district_arrival.append(district)

            transcript = (row.get("transcript") or "").strip()
            if not transcript:
                continue
            if per_district[district] >= cfg.per_cell:
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
            }
            manifest.write(json.dumps(record, ensure_ascii=False) + "\n")
            manifest.flush()
            rows.append(record)
            per_district[district] += 1

    _report_ordering(cfg.language, district_arrival)
    thin = [d for d, n in per_district.items() if n < cfg.min_cell]
    if thin:
        print(
            f"  {cfg.language}: {len(thin)} district(s) under {cfg.min_cell} clips "
            f"-> flagged low-confidence, not dropped: {', '.join(sorted(thin)[:6])}"
            + (" ..." if len(thin) > 6 else "")
        )
    print(
        f"  {cfg.language}: {len(rows)} new clips across {len(per_district)} districts "
        f"(scanned {scanned:,} rows)"
    )
    return rows


def _report_ordering(language: str, arrival: list[str]) -> None:
    """Warn if districts arrive in contiguous blocks.

    Streaming shuffle only reorders shards plus a local buffer. If a config
    stores one district per shard, an early stop would systematically miss the
    districts at the end of the file, which would bias the map. This check makes
    that visible instead of silent.
    """
    if len(arrival) < 100:
        return
    switches = sum(1 for a, b in zip(arrival, arrival[1:]) if a != b)
    distinct = len(set(arrival))
    if distinct > 1 and switches < distinct * 2:
        print(
            f"  ! {language}: districts arrive in blocks "
            f"({switches} switches over {distinct} districts in {len(arrival)} rows). "
            "Sampling may be biased toward early shards - raise max_scan or "
            "sample per-shard before trusting these cells."
        )
