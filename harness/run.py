"""Run providers over a sampled manifest and score the results.

Resumable by construction: every transcription is appended to a JSONL cache
keyed by (provider, clip_id) before scoring, so an interrupted run never pays
for the same clip twice.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from tqdm import tqdm

from harness.languages import get as get_language
from harness.providers.base import Provider, Transcription
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
) -> dict[str, dict]:
    """Transcribe every clip, skipping anything already cached."""
    cache = load_cache(cache_path)
    todo = [c for c in manifest if (provider.name, c["clip_id"]) not in cache]
    print(f"{provider.name}: {len(manifest) - len(todo)} cached, {len(todo)} to fetch")

    with cache_path.open("a") as out:
        for clip in tqdm(todo, desc=provider.name, unit="clip"):
            language = get_language(clip["language"])
            result: Transcription = provider.transcribe(
                str(data_dir / clip["wav"]), language.request_code
            )
            row = {
                "provider": provider.name,
                "clip_id": clip["clip_id"],
                **asdict(result),
            }
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
            cache[(provider.name, clip["clip_id"])] = row

    return {
        clip_id: row
        for (prov, clip_id), row in cache.items()
        if prov == provider.name
    }


def score_all(manifest: list[dict], transcripts: dict[str, dict], provider_name: str):
    scores = []
    for clip in manifest:
        row = transcripts.get(clip["clip_id"])
        scores.append(score_clip(clip, (row or {}).get("text"), provider_name))
    return scores


def summarize(scores, provider_name: str) -> dict:
    overall = aggregate(scores, by=("language",), min_clips=1)
    stats = district_mean_std(scores, "wer")
    errors = sum(s.empty_hypothesis for s in scores)

    print(f"\n=== {provider_name} ===")
    print(f"clips scored     : {len(scores)}")
    print(f"failed/empty     : {errors} ({errors / max(len(scores), 1):.1%})")
    for agg in sorted(overall, key=lambda a: -(a.primary or 0)):
        star = " *" if agg.low_confidence else ""
        wer = "n/a" if agg.wer is None else f"{agg.wer:.1%}"
        cer = "n/a" if agg.cer is None else f"{agg.cer:.1%}"
        print(
            f"  {agg.key[0]:<16} n={agg.clips:<5} WER {wer:>7}  CER {cer:>7}  "
            f"(primary: {agg.primary_metric}){star}"
        )
    if stats:
        mean, std = stats
        print(f"district mean WER: {mean:.1%} +/- {std:.1%}")

    return {
        "provider": provider_name,
        "clips": len(scores),
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
    raise ValueError(f"unknown provider {spec!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--providers", nargs="+", default=["sarvam:saaras:v3"])
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("data/results.json"))
    parser.add_argument("--cache", type=Path, default=Path("data/transcripts.jsonl"))
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    if args.limit:
        manifest = manifest[: args.limit]
    print(f"manifest: {len(manifest)} clips")

    summaries = []
    for spec in args.providers:
        provider = build_provider(spec)
        transcripts = transcribe_all(provider, manifest, args.data_dir, args.cache)
        scores = score_all(manifest, transcripts, provider.name)
        summaries.append(summarize(scores, provider.name))

    args.out.write_text(json.dumps({"runs": summaries}, indent=1, ensure_ascii=False))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
