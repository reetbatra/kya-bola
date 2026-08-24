# CONTEXT

The shared vocabulary for this repository. Use these words with these meanings.
One word has one meaning. Do not invent a synonym for a term that is here.

## The product

**Indic ASR Atlas** measures how well speech recognition works across India.
It reports the result by district and by language.

## Data terms

**Corpus**
: `ARTPARK-IISc/Vaani-transcription-part` on Hugging Face. It holds 1.38M
  transcribed clips in 64 languages. Its license is CC-BY-4.0. Always stream
  the corpus. Do not download it. It is 234 GB.

**Config**
: One language subset of the corpus. There are 64 configs.

**Clip**
: One audio recording with one transcript. A clip has a language, a state, a
  district, and a duration.

**Cell**
: One (language, district) pair. The sampler takes clips per cell.

**Manifest**
: The record of the sampled clips. One row per clip.

**Benchmark paper**
: arXiv 2606.21408, Vaani Benchmark V1.0. It scores 21 ASR systems on Hindi
  across 104 districts. It is the reference this project extends.

## Language terms

**Supported language**
: A corpus language that Sarvam STT accepts. There are 19 of these.

**Unsupported language**
: A corpus language that no commercial ASR API accepts. There are about 45.
  Send the audio anyway. Record what the API replies.

**Sarvam code**
: The BCP-47 code Sarvam STT accepts, for example `hi-IN`. Odia is `od-IN`,
  not `or-IN`.

**Detected language**
: The language the provider reports back when the request sends `unknown`.

## Provider terms

**Provider**
: One ASR backend. It implements `transcribe()` and returns a Transcription.
  A paid API and a local model look the same to the runner.

**Transcription**
: One provider answer for one clip. `text` is None when the provider failed.
  A failed clip is recorded. It is never dropped.

**Rate limiter**
: A token bucket. Sarvam Starter allows 60 requests per minute across the
  whole account. The limiter runs at 50.

**Checkpoint**
: The saved state of a run. A stopped run resumes. It does not bill twice.

## Scoring terms

**Reference**
: The human transcript from the corpus.

**Hypothesis**
: The text a provider returned.

**Normalization**
: The cleanup applied to both texts before comparison. It removes Unicode
  categories P and S. It keeps category M.

**Matra**
: A vowel sign in a Brahmic script. Its Unicode category is M. Deletion of
  matras makes WER look better and makes the score meaningless. Never remove
  category M.

**WER**
: Word error rate.

**CER**
: Character error rate.

**Primary metric**
: The metric to report first for a language. It is CER for agglutinative
  languages such as Tamil, Telugu, Kannada, and Malayalam. It is WER for the
  rest.

**Human disagreement floor**
: 10% to 15% WER. Two humans who transcribe the same audio differ by this
  much. A difference smaller than this is not a real difference.

## Map terms

**Crosswalk**
: The join from a Vaani district name to a geoBoundaries ADM2 polygon.
  Each entry is matched, review, or unmatched. An unmatched entry states a
  reason. No entry is dropped without a reason.

**ADM1**
: The state boundary layer.

**ADM2**
: The district boundary layer. It has 736 polygons. It carries `shapeName`
  only. `shapeISO` is empty, so there is no LGD code to join on.

**Low-confidence cell**
: A cell with fewer clips than the floor. Show the flag. Do not hide the cell.

## Run terms

**Calibration run**
: Sarvam Saaras v3 against the Hindi benchmark set. The district mean WER must
  land near 18.3 plus or minus 4.6. This gate protects every later number.

**Full run**
: All providers across the 64 languages and the 162 districts, on the same
  clips.
