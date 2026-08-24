"""WER/CER scoring with Indic-aware normalization.

Scoring lives in Python because the credible tooling (jiwer, indic-nlp-library)
is Python-only; there is no maintained Indic-aware WER package for JS/TS. The
web app reads precomputed results and never scores anything itself.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import asdict, dataclass

import jiwer

from harness.annotations import clean_reference
from harness.languages import get as get_language
from harness.normalize import normalize

# The Vaani team measured 10-15% WER between independent human transcribers of
# the same audio. Nothing below this is a real difference between models.
HUMAN_DISAGREEMENT_WER = (0.10, 0.15)


@dataclass(frozen=True)
class ClipScore:
    clip_id: str
    language: str
    district: str
    state: str
    provider: str
    wer: float | None
    cer: float | None
    ref_words: int
    ref_chars: int
    script: str
    empty_hypothesis: bool
    excluded: str | None
    reference_norm: str
    hypothesis_norm: str

    def as_dict(self) -> dict:
        return asdict(self)


def score_pair(
    reference: str,
    hypothesis: str | None,
    failure_kind: str | None = None,
) -> dict:
    """Score one reference/hypothesis pair.

    The reference is first stripped of Vaani transcriber annotations. Scored
    raw, `<noise>` tags and `{english}` glosses invent errors no model made.

    A None or blank hypothesis is a total miss (WER 1.0), not a skip -- an API
    that refuses to answer for an unsupported language has failed the clip, and
    dropping those rows would flatter every provider that gives up early.

    A reference the human transcriber marked unintelligible is a different case:
    the ground truth itself is untrustworthy, so it scores None and is excluded
    rather than blamed on the model.
    """
    if failure_kind == "infrastructure":
        # Quota exhausted, auth rejected, network dropped. The model never got
        # a fair shot at this clip, so it is excluded rather than scored 1.0.
        return {
            "wer": None, "cer": None, "ref_words": 0, "ref_chars": 0,
            "script": "Unknown", "empty_hypothesis": True,
            "reference_norm": "", "hypothesis_norm": "",
            "excluded": "provider_error",
        }

    cleaned = clean_reference(reference)
    if not cleaned.usable:
        return {
            "wer": None, "cer": None, "ref_words": 0, "ref_chars": 0,
            "script": "Unknown",
            "empty_hypothesis": not (hypothesis or "").strip(),
            "reference_norm": "", "hypothesis_norm": "",
            "excluded": "uncertain_reference" if cleaned.uncertain else "empty_reference",
        }

    ref_norm, script = normalize(cleaned.text)
    hyp_norm, _ = normalize(hypothesis or "", script=script)

    if not ref_norm:
        return {
            "wer": None, "cer": None, "ref_words": 0, "ref_chars": 0,
            "script": script, "empty_hypothesis": not hyp_norm,
            "reference_norm": "", "hypothesis_norm": hyp_norm,
            "excluded": "empty_reference",
        }

    if not hyp_norm:
        return {
            "wer": 1.0, "cer": 1.0,
            "ref_words": len(ref_norm.split()), "ref_chars": len(ref_norm),
            "script": script, "empty_hypothesis": True,
            "reference_norm": ref_norm, "hypothesis_norm": "",
            "excluded": None,
        }

    return {
        "wer": jiwer.wer(ref_norm, hyp_norm),
        "cer": jiwer.cer(ref_norm, hyp_norm),
        "ref_words": len(ref_norm.split()),
        "ref_chars": len(ref_norm),
        "script": script,
        "empty_hypothesis": False,
        "reference_norm": ref_norm,
        "hypothesis_norm": hyp_norm,
        "excluded": None,
    }


def score_clip(
    clip: dict,
    hypothesis: str | None,
    provider: str,
    failure_kind: str | None = None,
) -> ClipScore:
    """Score one manifest row against a provider's output."""
    result = score_pair(clip["transcript"], hypothesis, failure_kind)
    return ClipScore(
        clip_id=clip["clip_id"],
        language=clip["language"],
        district=clip["district"],
        state=clip["state"],
        provider=provider,
        **result,
    )


def _corpus_rate(scores: list[ClipScore], metric: str) -> float | None:
    """Length-weighted rate, the standard way to aggregate WER/CER.

    Averaging per-clip rates would let a three-word clip outweigh a thirty-word
    one. We weight by reference length instead, which is what jiwer does within
    a single call and what the published benchmarks report.
    """
    unit = "ref_words" if metric == "wer" else "ref_chars"
    total = sum(getattr(s, unit) for s in scores if getattr(s, metric) is not None)
    if not total:
        return None
    errors = sum(
        getattr(s, metric) * getattr(s, unit)
        for s in scores
        if getattr(s, metric) is not None
    )
    return errors / total


@dataclass(frozen=True)
class Aggregate:
    key: tuple
    provider: str
    clips: int
    scored: int
    excluded: int
    wer: float | None
    cer: float | None
    primary_metric: str
    primary: float | None
    empty_rate: float
    low_confidence: bool

    def as_dict(self) -> dict:
        d = asdict(self)
        d["key"] = list(self.key)
        return d


def aggregate(
    scores: list[ClipScore],
    by: tuple[str, ...] = ("language",),
    min_clips: int = 10,
) -> list[Aggregate]:
    """Group scores and compute length-weighted rates per group.

    Groups below `min_clips` are kept but flagged `low_confidence`, never
    silently dropped -- a missing district on the map is a lie, a greyed-out
    one is a finding.
    """
    buckets: dict[tuple, list[ClipScore]] = defaultdict(list)
    for s in scores:
        key = tuple(getattr(s, field) for field in by) + (s.provider,)
        buckets[key].append(s)

    out: list[Aggregate] = []
    for key, group in sorted(buckets.items()):
        *group_key, provider = key
        wer = _corpus_rate(group, "wer")
        cer = _corpus_rate(group, "cer")
        try:
            metric = get_language(group[0].language).primary_metric
        except KeyError:
            metric = "wer"
        out.append(
            Aggregate(
                key=tuple(group_key),
                provider=provider,
                clips=len(group),
                scored=sum(1 for s in group if s.excluded is None),
                excluded=sum(1 for s in group if s.excluded is not None),
                wer=wer,
                cer=cer,
                primary_metric=metric,
                primary=cer if metric == "cer" else wer,
                empty_rate=(
                    sum(s.empty_hypothesis for s in group if s.excluded is None)
                    / max(sum(1 for s in group if s.excluded is None), 1)
                ),
                low_confidence=sum(1 for s in group if s.excluded is None) < min_clips,
            )
        )
    return out


def district_mean_std(scores: list[ClipScore], metric: str = "wer") -> tuple[float, float] | None:
    """Mean and standard deviation across districts.

    This is the shape the Vaani Benchmark paper reports (e.g. Saaras v3 at
    18.3 +/- 4.6 for Hindi), so the calibration run compares against it
    directly rather than against a corpus-level number.
    """
    per_district = aggregate(scores, by=("district",), min_clips=1)
    values = [getattr(a, metric) for a in per_district if getattr(a, metric) is not None]
    if len(values) < 2:
        return None
    return statistics.mean(values), statistics.stdev(values)
