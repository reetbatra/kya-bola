"""Sample every language, then score every provider on the identical clips.

Ordered smallest-corpus-first. The unsupported languages are both the point of
the project and the cheapest to pull, so the coverage table fills in early and
a run that gets interrupted still has the finding in it.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(str(Path(__file__).resolve().parent.parent / ".env"))

from harness.languages import LANGUAGES  # noqa: E402
from harness.sample import SampleConfig, sample_language  # noqa: E402

OUT = Path("data")
MANIFEST = OUT / "manifest.jsonl"

PER_CELL = int(sys.argv[1]) if len(sys.argv) > 1 else 20
PER_SHARD = 50
MAX_SCAN = 5_000

order = sorted(LANGUAGES.values(), key=lambda language: language.clips)

print(f"{len(order)} languages, {PER_CELL} clips per (language, district) cell\n")
started = time.time()
for position, language in enumerate(order, 1):
    tag = "supported" if language.supported else "NO API SUPPORT"
    print(f"[{position}/{len(order)}] {language.name} ({language.clips:,} clips, {tag})")
    try:
        sample_language(
            SampleConfig(
                language=language.name,
                per_cell=PER_CELL,
                per_shard=PER_SHARD,
                max_scan=MAX_SCAN,
            ),
            OUT,
            manifest_path=MANIFEST,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"  ! {language.name} failed: {type(exc).__name__}: {exc}")
    print(f"  elapsed {(time.time() - started) / 60:.1f} min\n", flush=True)

print(f"sampling done in {(time.time() - started) / 60:.1f} min")
