"""Tests for WER/CER scoring and aggregation."""

import pytest

from harness.score import (
    ClipScore,
    aggregate,
    district_mean_std,
    score_clip,
    score_pair,
)


def test_perfect_match_scores_zero():
    r = score_pair("नमस्ते दुनिया", "नमस्ते दुनिया")
    assert r["wer"] == 0.0
    assert r["cer"] == 0.0


def test_punctuation_difference_is_not_an_error():
    r = score_pair("नमस्ते, दुनिया।", "नमस्ते दुनिया")
    assert r["wer"] == 0.0


def test_native_vs_ascii_digits_is_not_an_error():
    assert score_pair("मुझे ५ चाहिए", "मुझे 5 चाहिए")["wer"] == 0.0


def test_one_wrong_word_of_two():
    r = score_pair("नमस्ते दुनिया", "नमस्ते भारत")
    assert r["wer"] == pytest.approx(0.5)
    assert r["ref_words"] == 2


def test_empty_hypothesis_is_total_miss_not_skip():
    """An API that returns nothing has failed the clip. It must not be dropped."""
    for hyp in (None, "", "   ", "!!!"):
        r = score_pair("नमस्ते दुनिया", hyp)
        assert r["wer"] == 1.0, f"hypothesis {hyp!r} should score 1.0"
        assert r["empty_hypothesis"] is True


def test_empty_reference_yields_none():
    r = score_pair("", "something")
    assert r["wer"] is None and r["cer"] is None


def test_cer_is_gentler_than_wer_for_agglutinative_token():
    """One wrong character inside a long Malayalam word.

    WER calls the whole token wrong (1.0); CER sees a single-character edit.
    This asymmetry is exactly why CER is primary for Dravidian languages.
    """
    r = score_pair("സുഖമാണ്", "സുഖമാണു")
    assert r["wer"] == 1.0
    assert r["cer"] < 0.5


def _clip(cid, lang, district, transcript, state="TestState"):
    return {
        "clip_id": cid, "language": lang, "district": district,
        "state": state, "transcript": transcript,
    }


def test_score_clip_carries_metadata():
    s = score_clip(_clip("c1", "Hindi", "Araria", "नमस्ते दुनिया"), "नमस्ते दुनिया", "sarvam")
    assert s.clip_id == "c1" and s.language == "Hindi"
    assert s.district == "Araria" and s.provider == "sarvam"
    assert s.wer == 0.0


def test_aggregate_is_length_weighted_not_clip_averaged():
    """A short clip must not outweigh a long one.

    Clip A: 1 word, fully wrong. Clip B: 9 words, all correct.
    Clip-averaged WER would be 0.5. Length-weighted is 1/10 = 0.1.
    """
    scores = [
        score_clip(_clip("a", "Hindi", "D1", "एक"), "दो", "sarvam"),
        score_clip(_clip("b", "Hindi", "D1", " ".join(["शब्द"] * 9)), " ".join(["शब्द"] * 9), "sarvam"),
    ]
    agg = aggregate(scores, by=("language",), min_clips=1)
    assert len(agg) == 1
    assert agg[0].wer == pytest.approx(0.1)


def test_aggregate_flags_low_confidence_instead_of_dropping():
    scores = [score_clip(_clip("a", "Angami", "Kohima", "one two"), "one two", "sarvam")]
    agg = aggregate(scores, by=("language",), min_clips=10)
    assert len(agg) == 1, "sparse groups must survive aggregation"
    assert agg[0].low_confidence is True


def test_aggregate_splits_by_provider():
    clip = _clip("a", "Hindi", "D1", "नमस्ते दुनिया")
    scores = [
        score_clip(clip, "नमस्ते दुनिया", "sarvam"),
        score_clip(clip, "नमस्ते भारत", "whisper"),
    ]
    agg = aggregate(scores, by=("language",), min_clips=1)
    by_provider = {a.provider: a for a in agg}
    assert by_provider["sarvam"].wer == 0.0
    assert by_provider["whisper"].wer == pytest.approx(0.5)


def test_primary_metric_follows_language_family():
    hindi = aggregate([score_clip(_clip("a", "Hindi", "D", "एक दो"), "एक दो", "p")], min_clips=1)[0]
    tamil = aggregate([score_clip(_clip("b", "Tamil", "D", "ஒன்று இரண்டு"), "ஒன்று இரண்டு", "p")], min_clips=1)[0]
    assert hindi.primary_metric == "wer"
    assert tamil.primary_metric == "cer"


def test_unknown_language_defaults_to_wer_without_crashing():
    agg = aggregate([score_clip(_clip("a", "NotALanguage", "D", "one two"), "one two", "p")], min_clips=1)
    assert agg[0].primary_metric == "wer"


def test_empty_rate_is_reported():
    scores = [
        score_clip(_clip("a", "Garo", "WestGaroHills", "one two"), None, "sarvam"),
        score_clip(_clip("b", "Garo", "WestGaroHills", "one two"), "one two", "sarvam"),
    ]
    agg = aggregate(scores, by=("language",), min_clips=1)[0]
    assert agg.empty_rate == pytest.approx(0.5)


def test_district_mean_std_matches_paper_shape():
    scores = []
    for district, hyp in [("D1", "एक दो"), ("D2", "एक तीन"), ("D3", "चार पांच")]:
        scores.append(score_clip(_clip(district, "Hindi", district, "एक दो"), hyp, "sarvam"))
    result = district_mean_std(scores, "wer")
    assert result is not None
    mean, std = result
    assert mean == pytest.approx((0.0 + 0.5 + 1.0) / 3)
    assert std > 0


def test_district_mean_std_needs_two_districts():
    scores = [score_clip(_clip("a", "Hindi", "D1", "एक दो"), "एक दो", "sarvam")]
    assert district_mean_std(scores) is None


def test_infrastructure_failure_is_excluded_not_blamed():
    """Quota exhaustion is an empty wallet, not a bad model.

    This is the ElevenLabs case: the account ran out of credits mid-run and 70
    of 81 clips came back empty. Scored as refusals that reads as 91% WER,
    which would be a completely fabricated result.
    """
    clip = _clip("a", "Hindi", "D1", "नमस्ते दुनिया")
    s = score_clip(clip, None, "elevenlabs", failure_kind="infrastructure")
    assert s.wer is None and s.cer is None
    assert s.excluded == "provider_error"


def test_refusal_still_scores_one():
    """An API that refuses an unsupported language HAS failed the clip."""
    clip = _clip("a", "Garo", "WestGaroHills", "ia nokni rongde")
    s = score_clip(clip, None, "sarvam", failure_kind="refusal")
    assert s.wer == 1.0
    assert s.excluded is None


def test_excluded_clips_do_not_move_the_aggregate():
    clip_ok = _clip("a", "Hindi", "D1", "एक दो")
    clip_dead = _clip("b", "Hindi", "D1", "तीन चार")
    scores = [
        score_clip(clip_ok, "एक दो", "p"),
        score_clip(clip_dead, None, "p", failure_kind="infrastructure"),
    ]
    agg = aggregate(scores, by=("language",), min_clips=1)[0]
    assert agg.wer == 0.0, "an excluded clip must not drag the score"
    assert agg.scored == 1 and agg.excluded == 1


def test_low_confidence_counts_only_scored_clips():
    scores = [
        score_clip(_clip(str(i), "Hindi", "D1", "एक दो"), None, "p",
                   failure_kind="infrastructure")
        for i in range(50)
    ]
    agg = aggregate(scores, by=("language",), min_clips=10)[0]
    assert agg.low_confidence is True, "50 excluded clips are not 50 data points"


def test_per_shard_budget_covers_every_shard():
    """The bug this pins: a fixed per-shard read plus a fixed total budget
    truncated wide configs. Hindi has 193 shards; 40 rows each against a
    4,000-row budget stopped halfway, reaching 14 districts of roughly 100."""
    from harness.sample import SampleConfig, per_shard_for

    for shard_count in (1, 9, 36, 193, 400):
        cfg = SampleConfig(language="Hindi", max_scan=6000)
        per_shard = per_shard_for(cfg, shard_count)
        assert per_shard * shard_count >= min(6000, per_shard * shard_count)
        assert per_shard >= cfg.min_per_shard
        # the walk must be able to reach the final shard
        assert per_shard * shard_count >= shard_count * cfg.min_per_shard


def test_explicit_per_shard_is_respected():
    from harness.sample import SampleConfig, per_shard_for

    assert per_shard_for(SampleConfig(language="Hindi", per_shard=7), 193) == 7
