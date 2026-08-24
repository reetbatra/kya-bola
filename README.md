# indic-asr-atlas

A district- and language-level benchmark of Indian speech recognition, built on
the Vaani corpus from ARTPARK/IISc.

## What this is

Every ASR vendor reports accuracy per language. Hindi in Delhi and Hindi in
Araria are not the same problem, and a single number hides that. This project
scores commercial and open ASR systems per `(language, district)` and publishes
the result as a map plus a coverage table.

The Vaani team already published a Hindi-only district benchmark
([arXiv 2606.21408](https://arxiv.org/abs/2606.21408)). This extends it to the
other 63 languages in the corpus, keeps it reproducible, and makes it
interactive.

## Layout

- `harness/` — Python. Sampling, providers, scoring, the district crosswalk.
- `web/` — Next.js site reading precomputed results. No Python at request time.
- `data/` — boundary files, crosswalk, results JSON. Audio is never committed.

## Rules that matter here

- **Never strip Unicode category M when normalizing Indic text.** Matras and the
  virama are category M. Whisper's `BasicTextNormalizer` strips M, S and P
  together and silently deletes the vowels, which makes WER look better while
  destroying the comparison. `harness/normalize.py` explains this and
  `test_normalize.py` pins it across 11 scripts.
- **CER is the primary metric for Dravidian languages.** One wrong morpheme
  inside a long agglutinated token marks the whole word wrong under WER.
- **A failed transcription is a score of 1.0, not a dropped row.** An API that
  refuses an unsupported language has failed the clip. Dropping those rows would
  flatter whichever provider gives up most often.
- **Never download the corpus.** It is 234 GB. Stream it.
- **Flag, never drop.** Sparse cells get `low_confidence`; districts with no
  polygon get a documented reason. A hole in a map reads as "no problem here".
- Secrets live in `.env`, referenced by name. Never in source, never in commits.

## Commands

```bash
uv sync                                 # set up (Python 3.12)
uv run pytest                           # tests
./scripts/fetch_boundaries.sh           # download India ADM1/ADM2
uv run python -m harness.crosswalk      # rebuild the district join
```
