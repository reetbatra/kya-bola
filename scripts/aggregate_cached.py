"""Write results.json from whatever is already in the transcription cache.

Scores only clips that have been transcribed, so the site can be built and
checked while a run is still in flight. No API calls.
"""
from __future__ import annotations

import json
from pathlib import Path

from harness.run import load_cache, load_manifest, score_all, summarize

OUT = Path("data")


def main() -> None:
    manifest = load_manifest(OUT / "manifest.jsonl")
    cache = load_cache(OUT / "transcripts.jsonl")
    providers = sorted({provider for provider, _ in cache})

    summaries = []
    for provider in providers:
        rows = {cid: row for (p, cid), row in cache.items() if p == provider}
        subset = [c for c in manifest if c["clip_id"] in rows]
        if not subset:
            continue
        summaries.append(summarize(score_all(subset, rows, provider), provider))

    (OUT / "results.json").write_text(
        json.dumps({"runs": summaries}, indent=1, ensure_ascii=False)
    )
    print(f"\nwrote data/results.json from {len(cache)} cached transcriptions")


if __name__ == "__main__":
    main()
