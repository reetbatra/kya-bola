"""Run providers over a sampled manifest and score the results.

Resumable by construction: every transcription is appended to a JSONL cache
keyed by (provider, clip_id) before scoring, so an interrupted run never pays
for the same clip twice.
"""

from __future__ import annotations

import argparse
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path

from tqdm import tqdm

from harness.languages import get as get_language
from harness.providers.base import Provider, ProviderQuotaError, Transcription
from harness.score import aggregate, district_mean_std, score_clip


def load_manifest(path: Path) -> list[dict]:
    with path.open() as fh:
        return [json.loads(line) for line in fh if line.strip()]


def load_cache(path: Path) -> dict[tuple[str, str], dict]:
    if not path.exists():
        return {}
    cache: dict[tuple[str, str], dict] = {}
    with path.open() as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            cache[(row["provider"], row["clip_id"])] = row
    return cache


def transcribe_all(
    provider: Provider,
    manifest: list[dict],
    data_dir: Path,
    cache_path: Path,
    workers: int = 4,
) -> dict[str, dict]:
    """Transcribe every clip, skipping anything already cached.

    Requests run concurrently because each one spends most of its time
    uploading audio rather than waiting on the rate limiter. Sequentially the
    Sarvam run measured about 15 calls/min against a 50/min budget. The shared
    RateLimiter still enforces the account-wide ceiling across threads, so
    concurrency spends the quota rather than exceeding it.
    """
    cache = load_cache(cache_path)
    todo = [c for c in manifest if (provider.name, c["clip_id"]) not in cache]
    print(f"{provider.name}: {len(manifest) - len(todo)} cached, {len(todo)} to fetch")

    write_lock = threading.Lock()
    quota_hit = threading.Event()

    def run_one(clip: dict) -> None:
        if quota_hit.is_set():
            return
        language = get_language(clip["language"])
        try:
            result: Transcription = provider.transcribe(
                str(data_dir / clip["wav"]), language.request_code
            )
        except ProviderQuotaError as exc:
            # Stop everything. Continuing would write rows that look like model
            # failures but are really an empty wallet.
            if not quota_hit.is_set():
                quota_hit.set()
                print(f"\n!! {exc}")
                print(f"!! stopping {provider.name}")
            return
        row = {"provider": provider.name, "clip_id": clip["clip_id"], **asdict(result)}
        with write_lock:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
            cache[(provider.name, clip["clip_id"])] = row

    with cache_path.open("a") as out:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(
                tqdm(
                    pool.map(run_one, todo),
                    total=len(todo),
                    desc=provider.name,
                    unit="clip",
                )
            )

    return {
        clip_id: row
        for (prov, clip_id), row in cache.items()
        if prov == provider.name
    }


def score_all(manifest: list[dict], transcripts: dict[str, dict], provider_name: str):
    scores = []
    for clip in manifest:
        row = transcripts.get(clip["clip_id"]) or {}
        kind = row.get("failure_kind")
        if not row:
            # Never attempted (run stopped early). Exclude, do not blame.
            kind = "infrastructure"
        scores.append(score_clip(clip, row.get("text"), provider_name, kind))
    return scores


def summarize(scores, provider_name: str) -> dict:
    overall = aggregate(scores, by=("language",), min_clips=1)
    stats = district_mean_std(scores, "wer")
    scored = [s for s in scores if s.excluded is None]
    excluded = len(scores) - len(scored)
    errors = sum(s.empty_hypothesis for s in scored)

    print(f"\n=== {provider_name} ===")
    print(f"clips scored     : {len(scored)} of {len(scores)} ({excluded} excluded)")
    print(f"model returned nothing: {errors} ({errors / max(len(scored), 1):.1%})")
    for agg in sorted(overall, key=lambda a: -(a.primary or 0)):
        star = " *" if agg.low_confidence else ""
        wer = "n/a" if agg.wer is None else f"{agg.wer:.1%}"
        cer = "n/a" if agg.cer is None else f"{agg.cer:.1%}"
        print(
            f"  {agg.key[0]:<16} n={agg.scored:<5} WER {wer:>7}  CER {cer:>7}  "
            f"(primary: {agg.primary_metric}){star}"
        )
    if stats:
        mean, std = stats
        print(f"district mean WER: {mean:.1%} +/- {std:.1%}")

    return {
        "provider": provider_name,
        "clips": len(scores),
        "scored": len(scored),
        "excluded": excluded,
        "empty": errors,
        "by_language": [a.as_dict() for a in overall],
        "by_district": [a.as_dict() for a in aggregate(scores, by=("district",), min_clips=1)],
        "by_language_district": [
            a.as_dict() for a in aggregate(scores, by=("language", "district"), min_clips=1)
        ],
        "district_mean_wer": stats[0] if stats else None,
        "district_std_wer": stats[1] if stats else None,
    }


def build_provider(spec: str) -> Provider:
    if spec.startswith("sarvam:"):
        from harness.providers.sarvam import SarvamProvider

        return SarvamProvider(model=spec.split("sarvam:", 1)[1])
    if spec.startswith("elevenlabs"):
        from harness.providers.elevenlabs import DEFAULT_MODEL, ElevenLabsProvider

        _, _, model = spec.partition(":")
        return ElevenLabsProvider(model=model or DEFAULT_MODEL)
    if spec.startswith("indicconformer"):
        from harness.providers.indicconformer import IndicConformerProvider

        _, _, decoding = spec.partition(":")
        return IndicConformerProvider(decoding=decoding or "ctc")
    raise ValueError(f"unknown provider {spec!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--providers", nargs="+", default=["sarvam:saaras:v3"])
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("data/results.json"))
    parser.add_argument("--cache", type=Path, default=Path("data/transcripts.jsonl"))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    if args.limit:
        manifest = manifest[: args.limit]
    print(f"manifest: {len(manifest)} clips")

    summaries = []
    for spec in args.providers:
        provider = build_provider(spec)
        transcripts = transcribe_all(
            provider, manifest, args.data_dir, args.cache, args.workers
        )
        scores = score_all(manifest, transcripts, provider.name)
        summaries.append(summarize(scores, provider.name))

    args.out.write_text(json.dumps({"runs": summaries}, indent=1, ensure_ascii=False))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
