"""Sample every language, in parallel, skipping whatever is already done.

Sampling is network bound, not CPU bound, so several languages run at once.
Each worker owns its own manifest to avoid interleaved writes; `merge` stitches
them together afterwards.

Ordered smallest-corpus-first. The unsupported languages are both the point of
the project and the cheapest to pull, so the coverage table fills in early and
an interrupted run still contains the finding.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(str(Path(__file__).resolve().parent.parent / ".env"))

from harness.languages import LANGUAGES  # noqa: E402
from harness.sample import SampleConfig, sample_language  # noqa: E402

OUT = Path("data")
MERGED = OUT / "manifest.jsonl"
PER_CELL = 20
PER_SHARD = 40
MAX_SCAN = 4_000


def done_languages() -> set[str]:
    """Languages already represented in any manifest on disk."""
    seen: set[str] = set()
    for path in list(OUT.glob("manifest*.jsonl")):
        with path.open() as fh:
            for line in fh:
                if line.strip():
                    seen.add(json.loads(line)["language"])
    return seen


def worker(index: int, total: int) -> None:
    order = sorted(LANGUAGES.values(), key=lambda language: language.clips)
    done = done_languages()
    mine = [l for i, l in enumerate(order) if i % total == index and l.name not in done]
    manifest = OUT / f"manifest.worker{index}.jsonl"

    print(f"worker {index}: {len(mine)} languages", flush=True)
    started = time.time()
    for position, language in enumerate(mine, 1):
        tag = "supported" if language.supported else "NO API SUPPORT"
        print(f"[w{index} {position}/{len(mine)}] {language.name} "
              f"({language.clips:,} clips, {tag})", flush=True)
        try:
            sample_language(
                SampleConfig(
                    language=language.name,
                    per_cell=PER_CELL,
                    per_shard=PER_SHARD,
                    max_scan=MAX_SCAN,
                ),
                OUT,
                manifest_path=manifest,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  ! {language.name} failed: {type(exc).__name__}: {exc}", flush=True)
        print(f"  [w{index}] elapsed {(time.time() - started) / 60:.1f} min\n", flush=True)
    print(f"worker {index} done in {(time.time() - started) / 60:.1f} min", flush=True)


def merge() -> None:
    """Concatenate worker manifests into data/manifest.jsonl, deduped."""
    seen: set[str] = set()
    rows: list[str] = []
    for path in sorted(OUT.glob("manifest*.jsonl")):
        with path.open() as fh:
            for line in fh:
                if not line.strip():
                    continue
                cid = json.loads(line)["clip_id"]
                if cid in seen:
                    continue
                seen.add(cid)
                rows.append(line if line.endswith("\n") else line + "\n")
    MERGED.write_text("".join(rows))
    print(f"merged {len(rows)} clips into {MERGED}")


if __name__ == "__main__":
    if sys.argv[1] == "merge":
        merge()
    else:
        worker(int(sys.argv[1]), int(sys.argv[2]))
