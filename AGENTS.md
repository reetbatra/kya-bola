# kya bola?

*"kya bola?" means "what did you say?" It is what you ask when you did not catch it.*
*Also, apparently, what most speech APIs are thinking once you leave the metros.*

A district-level and language-level benchmark of Indian speech recognition,
built on [Project Vaani](https://huggingface.co/datasets/ARTPARK-IISc/Vaani)
from ARTPARK and IISc.

## Why

Every speech recognition vendor publishes one accuracy number per language.
Hindi in Delhi and Hindi in Araria are not the same problem, and one number
hides the difference.

There is a second gap underneath that one. The Vaani transcribed corpus
contains **64 languages**. Commercial speech APIs officially support **19** of
them. Nobody has published what happens to the other 45, which include Garo
(41,834 transcribed clips), Chakma (41,140), Nagamese, Bhojpuri, Mizo,
Chhattisgarhi, Wancho, Kokborok, Tulu, Gondi and Kurukh.

## Standing on published work

The Vaani team already benchmarked 21 ASR systems on their own Hindi evaluation
set, across 104 districts, in [arXiv 2606.21408](https://arxiv.org/abs/2606.21408).
That paper is the reason this project exists in its current shape: the district
map for Hindi is theirs, and repeating it would add nothing.

This extends the idea to the other 63 languages, makes it reproducible, and
keeps it current as new models ship.

Before measuring anything new, the harness reproduces their published result
for Sarvam Saaras v3 on their own clips:

| metric | this harness | published | delta |
|---|---|---|---|
| approach 1 | 18.7% | 20.3% | −1.6pt |
| approach 2 | 15.9% | 16.9% | −1.0pt |
| district mean WER | 17.6% | 18.3% | −0.7pt |
| district std | 7.7% | 4.6% | +3.1pt |
| human v1 vs v2 WER | 9.4% | 10–15% (stated) | matches |

350 clips across 90 of their 104 districts. The district standard deviation is
higher because this samples 4 clips per district where the paper uses roughly
48; fewer clips per district makes each district mean noisier. Approach 3 is
not reproduced, because the paper describes it only as "alignment across
references" and guessing at the implementation would produce a number that
agrees or disagrees for unknown reasons.

## The floor

Two humans transcribing the same Vaani audio disagree with each other by about
**9.4% WER**, measured here directly from the benchmark's three independent
reference transcriptions. The paper puts the same figure at 10–15%.

No model can score below that, and no gap narrower than it distinguishes two
systems. The site draws it on the chart rather than burying it in a footnote.

## Things that will quietly ruin a benchmark like this

Each of these was found by running the thing, and each is pinned by a test.

**Never strip Unicode category M from Indic text.** Matras and the virama are
category M. The widely copied Whisper `BasicTextNormalizer` strips M, S and P
together, which deletes the vowels from every Brahmic script and makes WER look
better while destroying the comparison. A documented case takes Malayalam from
16.6% to 7.69% purely through this corruption.

**Vaani transcripts carry transcriber annotations.** Measured over 750
transcripts: paired `<noise>` and `<pause>` tags in 56.3%, `{english}` glosses
in 35.5%, `[event]` notes in 10.1%, `--` truncation markers in 15.3%. Scoring
the raw strings inflates WER by **18.4 points**.

The tags are paired and wrap real speech. In Garo the entire utterance sits
inside `<noise> ... </noise>`, so removing tag and content would empty the
reference for more than half the clips. The braces are the opposite case:
`साइड {side}` is one spoken word written twice, natively and then glossed, so
the brace group must go entirely.

Tag names can contain spaces. `<static noise>` appears in the benchmark set,
and a pattern that assumed one word left "static noise" in the reference as two
phantom words, which alone pushed measured human disagreement from 9.4% to
32.9%.

**A failed transcription and an exhausted quota are not the same event.** An API
that refuses an unsupported language has genuinely failed the clip and scores
1.0; dropping those rows would flatter whichever provider gives up most often.
An account out of credits never gave the model a fair shot, so the clip is
excluded and the run aborts. Conflating them produced a 91.3% WER for a
provider that was simply out of money.

**WER over-punishes Dravidian languages.** One long agglutinated token can carry
a whole clause, so a single wrong morpheme marks the entire word wrong. CER is
reported as primary for Tamil, Telugu, Kannada, Malayalam, Tulu, Gondi, Kurukh
and Bearybashe.

**Sampling has to walk shards.** Hindi has 193 training shards. Streaming a
config sequentially reads from the front and stops when the scan budget runs
out, which reached 15 districts out of roughly a hundred. District coverage
should be a property of the sampler, not an accident of where the budget ran
out.

**The map has legal constraints.** District polygons come from geoBoundaries
`gbOpen` IND ADM2, which is derived from India's own LGD directory. The
per-country file is used deliberately: geoBoundaries' CGAZ composite follows US
State Department definitions for disputed areas, which do not match India's
official boundary.

## Caveats that belong next to every number

- The audio is spontaneous, image-prompted speech recorded in real acoustic
  conditions, not read speech in a studio. Error rates here are legitimately
  higher than the figures vendors publish on clean benchmarks.
- Scoring uses a single reference outside the calibration set, which has three.
- Districts below the clip floor are flagged `low_confidence`, never dropped.
- Four districts with Vaani audio have no polygon in the 2021 boundary release
  (Charkhi Dadri, created 2016; Annamayya, Parvathipuram Manyam and Sri Sathya
  Sai, created 2022). They are named on the site rather than left as a gap.

## Layout

- `harness/`: Python. Sampling, providers, scoring, calibration, the district crosswalk.
- `web/`: Next.js site reading precomputed JSON. Nothing is scored at request time.
- `data/`: boundary files, crosswalk, results. Audio is never committed.

## Rules for agents working here

- Never strip Unicode category M. See above.
- Flag, never drop: sparse cells get `low_confidence`, unmapped districts get a documented reason.
- Never download the corpus, it is 234 GB. Stream it.
- Raise errors explicitly. No silent fallbacks.

## Running it

```bash
uv sync                                   # Python 3.12
uv run pytest                             # 80 tests
./scripts/fetch_boundaries.sh             # India ADM1/ADM2 from geoBoundaries
uv run python -m harness.crosswalk        # rebuild the district join
uv run python -m harness.calibrate        # reproduce the published numbers
uv run python scripts/full_run.py 20      # sample every language
```

Secrets go in `.env` (`SARVAM_API_KEY`, `HF_TOKEN`, `ELEVENLABS_API_KEY`), never
in source.

## Attribution

Vaani is CC-BY-4.0, by ARTPARK and IISc, funded by Google. Boundary data is
geoBoundaries under ODbL 1.0. The benchmark methodology follows
Pulikodan et al., *Vaani Benchmark V1.0*, arXiv 2606.21408.
