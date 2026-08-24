# Draft note to Sarvam (NOT SENT)

Reet to send, or not, after reading. Nothing goes out without an explicit go.

---

**Subject:** Extended your Vaani benchmark to the other 63 languages

Hi [name],

Following up on our conversation. I built something with your API rather than
writing you another email about wanting to.

Your team's Vaani Benchmark V1.0 paper benchmarks 21 ASR systems on Hindi across
104 districts. I extended the same idea to the rest of the corpus: all 64
languages in Vaani-transcription-part, scored per district, on a live map.

Two things before the findings.

First, I reproduced your published Saaras v3 numbers before measuring anything
new. On your own clips my pipeline gets 18.7 / 15.9 / 17.6 against your
published 20.3 / 16.9 / 18.3, so within about 1.5 points on every approach. I
also independently measured your three-reference inter-annotator disagreement at
9.4%, against the 10 to 15% the paper states.

Second, Saaras v4 beats v3 consistently in my runs, and both beat every other
commercial API I could test.

The finding I did not expect: the official language support list barely predicts
whether a language works. Magahi is not on it and scores 16.8%. Santali is on it
and scores 84.2%. Across the corpus the supported and unsupported distributions
overlap heavily.

Two things in there are probably useful to you regardless of what happens with
any role:

1. Kashmiri measures 63.9% WER with standard normalization and 35.7% once
   Arabic short-vowel marks are stripped from both sides. Anyone benchmarking
   your Kashmiri support without that step is reporting a number roughly 28
   points worse than reality.
2. For the 45 unsupported languages, auto-detect returns confident output in the
   wrong language rather than declining. Several score above 100% WER, which
   means insertions. A "we do not support this" signal would be more useful to a
   developer than fluent Hindi for a Tagin speaker.

Everything is open source, including the harness, the normalization rules and
the tests: [repo link]
The map: [site link]
Writeup: [post link]

I would rather you see it before it is public. If anything is wrong I would like
to fix it before anyone else reads it, and if any of it is useful, take it.

Reet

---

## Notes before sending

- Fill in the name, and the three links.
- The PR on sarvamai/skills (#17) is still open. Worth mentioning only if it has
  not been merged by the time this goes out.
- Do not send until the map has most of its districts. The argument rests on
  breadth of coverage.
- Tone check: this offers them something. It is not a request.
