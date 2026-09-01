# India speaks 64 languages in this dataset. Speech APIs support 19.

Every speech recognition vendor publishes one accuracy number per language.
One figure for Hindi, one for Tamil. Tidy, and close to meaningless, because
Hindi in Delhi and Hindi in Araria aren't the same problem.

I wanted to know how big that difference actually is, so I measured it district
by district.

## What I did

Project Vaani is a speech corpus from ARTPARK and IISc: ordinary Indians
describing photographs, recorded in their own homes and streets, tagged by
district. The transcribed portion covers 2,043 hours across 165 districts, and
every clip carries a human transcript to score against.

I sampled clips per district, sent them to commercial and open speech APIs,
compared each result against its human transcript, and drew the answer on a map.

## The part I expected

Accuracy varies a lot by geography. Within Hindi alone the best districts land
around 7% word error rate and the worst around 33%. One national number hides a
fivefold difference in whether this technology works for you.

## The part I didn't expect

The corpus contains 64 languages. Sarvam's speech API documents 23. The
overlap is 19, which leaves 45 languages spoken by real people in this dataset
that no commercial API claims to handle at all.

I sent them anyway, with language detection turned on, because that is what a
developer building for those speakers would do.

| language | official support | word error rate |
|---|---|---|
| Tagin | no | 122.7% |
| Nyishi | no | 120.2% |
| Sumi | no | 116.2% |
| Kokborok | no | 107.9% |
| Angami | no | 97.4% |
| ... | | |
| Santali | **yes** | 84.2% |
| Kashmiri | **yes** | 35.7% |
| ... | | |
| Magahi | no | 16.8% |
| Khariboli | no | 18.0% |
| Bundeli | no | 25.3% |

Rates above 100% are not a bug. Word error rate counts insertions, so a model
returning more words than were spoken can exceed the length of the reference.
It means the model is not declining to answer. It is confidently producing
fluent text in the wrong language.

Look at the bottom of that table, though. Magahi is on nobody's support list and
scores 16.8%. Santali is on the official list and scores 84.2%. The median
supported language sits around 36% and the median unsupported one around 66%,
but the two ranges overlap so heavily that the support list barely predicts
anything.

So the finding isn't that the API is bad. It clearly isn't. It's that the
published support list and the actual behaviour are two different things, and
only one of them is written down anywhere.

## Three systems, and the open one holds up

Once the free option was in, the comparison stopped being a walkover. On the 19
languages all three support:

| language | IndicConformer | Saaras v3 | Saaras v4 |
|---|---|---|---|
| Hindi | **19.5%** | 22.2% | 21.0% |
| Urdu | **36.5%** | 48.8% | 47.8% |
| Manipuri | **21.4%** | 26.7% | 26.7% |
| Tamil | 27.0% | 32.0% | **22.7%** |
| Odia | 56.3% | 60.5% | **41.9%** |
| Santali | 83.2% | 84.2% | **58.6%** |

AI4Bharat's IndicConformer is MIT licensed, runs on a laptop, costs nothing,
and beats a paid API on Hindi, Urdu and Manipuri. Saaras v4 wins clearly on
Santali, Odia and Tamil, and beats v3 almost everywhere. If you are building for
one specific language, the ranking is language by language and the vendor
comparison table on anyone's marketing page will not tell you which.

IndicConformer also refuses outright for the 45 languages it does not cover,
which is worth something. Refusing is more useful to a developer than fluent
Hindi returned for a Tagin speaker.

## Why you should believe the numbers

Before measuring anything new, I reproduced a published result.

The Vaani team benchmarked 21 ASR systems on their own Hindi evaluation set and
reported Sarvam Saaras v3 at a district mean word error rate of 18.3%. Running
their clips through my pipeline:

| metric | mine | published | delta |
|---|---|---|---|
| approach 1 | 18.7% | 20.3% | −1.6pt |
| approach 2 | 15.9% | 16.9% | −1.0pt |
| district mean | 17.6% | 18.3% | −0.7pt |

Their benchmark also carries three independent human transcriptions per clip,
which lets me measure something more useful than any model score: **two humans
transcribing the same audio disagree with each other by 9.4%.** The paper puts
that figure at 10 to 15%.

That is the floor. No model can score below it, and no gap narrower than it
distinguishes two systems. The map draws it as a single colour band rather than
a smooth gradient, because a gradient would invent differences the data cannot
support.

## Four ways I nearly published something false

Each of these gave me numbers that looked completely reasonable and were wrong.

**Deleting the vowels.** The Whisper text normalizer that most evaluation code
copies strips Unicode categories M, S and P together. In every Brahmic script
the vowel signs and the virama are category M. Applied to Indic text it deletes
the vowels, and because it deletes them from both sides, error rates improve.
There's a documented case of Malayalam "improving" from 16.6% to 7.69% purely
from this corruption. The score gets better because the comparison gets emptier.

**Scoring the annotations.** Vaani transcripts carry transcriber markup:
`<noise>` tags, `[breathing]` notes, `--` truncations, and `{english}` glosses.
Scored raw, that inflated word error rate by **18.4 points**. The tags are
paired and wrap real speech, so removing tag and content would have emptied the
reference for more than half the Garo clips. The braces are the opposite:
`साइड {side}` is one spoken word written twice, natively and then glossed.

Then the same bug wearing a disguise. The benchmark set writes `<static noise>`
with a space in the tag name. My pattern assumed one word, so "static noise"
stayed in the reference as two words no model could ever say. That alone moved
measured human-versus-human disagreement from 9.4% to 32.9%.

**Counting an empty wallet as a bad model.** A run against a second provider ate
its quota after 11 clips. The other 70 came back empty and scored as total
failures, which produced a very tidy 91.3% error rate describing my billing
status rather than anything about the model. Refusals and infrastructure failures now go in
different buckets: an API that rejects an unsupported language has genuinely
failed the clip, an API that has run out of credit never got to try.

**Counting diacritic order as errors.** Kashmiri looked broken at 63.9%, so I
opened the transcripts. Reference `چُھ`, hypothesis `چھُ`. Same letters, same
word, different order for an optional vowel mark that Unicode doesn't reorder.
Kashmiri is 35.7%. I was one commit away from publishing a claim about a
vendor's Kashmiri support that was off by 28 points.

What connects all four: a wrong number here doesn't look wrong. It looks like a
finding. Three of the four made the story better, which is exactly why I'd have
kept them. The only defences I found were reproducing somebody else's published
result before trusting my own, and reading the actual text instead of the
summary statistic.

## Caveats

- This is spontaneous, image-prompted speech recorded in real acoustic
  conditions, not read speech in a studio. Error rates here are legitimately
  higher than the figures vendors publish on clean benchmarks.
- Outside the calibration set there is one reference transcript per clip, not
  three.
- Districts below the clip floor are flagged rather than dropped.
- Four districts with Vaani audio have no polygon in the 2021 boundary release,
  because they were created in 2016 and 2022. They are named on the site instead
  of leaving a silent gap in the map.

## The code

The harness, the district crosswalk, the normalization rules and every test are
in the repository. Scoring is model-agnostic, so adding another provider is one
file.

Built on Project Vaani by ARTPARK and IISc, used under CC-BY-4.0. Benchmark
methodology follows Pulikodan et al., *Vaani Benchmark V1.0*, arXiv 2606.21408.
