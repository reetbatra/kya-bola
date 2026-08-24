"""Tests for Vaani transcriber-annotation cleaning.

Every literal below is a real transcript pulled from
ARTPARK-IISc/Vaani-transcription-part on 2026-08-24, not a synthetic example.
"""

import pytest

from harness.annotations import clean_reference


def test_paired_tags_keep_their_speech():
    """The failure that would have emptied 56% of references."""
    raw = "<noise> ia nokni rongde rimit rong ong·a. </noise>"
    out = clean_reference(raw)
    assert out.text == "ia nokni rongde rimit rong ong·a."
    assert not out.empty_after_clean
    assert out.removed["tags"] == 2


def test_garo_middle_dot_survives_cleaning():
    """U+00B7 is a letter in Garo orthography, not punctuation."""
    assert "·" in clean_reference("<noise> ong·a nika </noise>").text


def test_gloss_is_removed_entirely():
    """`साइड {side}` is one word written twice. Keeping the gloss invents a word."""
    out = clean_reference("यहां पे चारों साइड {side} में --")
    assert out.text == "यहां पे चारों साइड में"
    assert "side" not in out.text
    assert out.removed["glosses"] == 1


def test_event_markers_are_removed_with_content():
    out = clean_reference("<noise> [unintelligible] ning·o bimangko dake </noise>")
    assert "unintelligible" not in out.text
    assert out.text == "ning·o bimangko dake"


def test_unintelligible_is_flagged_not_silently_kept():
    out = clean_reference("यह [unintelligible] है")
    assert out.uncertain is True
    assert out.usable is False, "untrustworthy ground truth must not be scored"


def test_inaudible_also_flags():
    assert clean_reference("कुछ [inaudible] बात").uncertain is True


def test_ordinary_event_markers_do_not_flag_uncertain():
    out = clean_reference("<noise> सुंदर [inhaling] दृश्य </noise>")
    assert out.uncertain is False
    assert out.usable is True
    assert out.text == "सुंदर दृश्य"


def test_truncation_marker_removed():
    out = clean_reference("तरिगिपाओ चोलारंगको--")
    assert "--" not in out.text
    assert out.removed["truncations"] == 1


def test_quote_runs_removed():
    out = clean_reference("''<noise> स्टील {steel} की तथा </noise>")
    assert "''" not in out.text
    assert out.text == "स्टील की तथा"


def test_clean_transcript_is_untouched():
    raw = "बहुत ही सुन्दर टमाटर है ।"
    assert clean_reference(raw).text == raw


def test_multiple_glosses_in_one_line():
    out = clean_reference("मशीन {machine} भी और एकिपमेंट {equipment''''s} भी")
    assert "machine" not in out.text and "equipment" not in out.text
    assert out.removed["glosses"] == 2


def test_tag_only_reference_is_empty_and_flagged():
    out = clean_reference("<noise> [noise] </noise>")
    assert out.empty_after_clean is True
    assert out.usable is False


def test_open_tag_vocabulary():
    """Tags are matched structurally; <talking> was not in the original list."""
    out = clean_reference("<talking> तो ये आर्टिफिशियल {artificial} है </talking>")
    assert out.text == "तो ये आर्टिफिशियल है"


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_empty_inputs(raw):
    out = clean_reference(raw)
    assert out.empty_after_clean is True
    assert out.text == ""


def test_tag_names_may_contain_spaces():
    """`<static noise>` is real, from Vaani-Benchmark-V1.0.

    A pattern that required a single-word tag name left "static noise" in the
    reference as two phantom words, inflating every score computed against it.
    """
    out = clean_reference("<static noise> होटल का नेम पिकाडू है। </static noise>")
    assert out.text == "होटल का नेम पिकाडू है।"
    assert "static" not in out.text and "noise" not in out.text


def test_uppercase_tags():
    assert clean_reference("यहाँ पे <PAUSE> बहुत सारा").text == "यहाँ पे बहुत सारा"


def test_hyphenated_tag_names():
    assert clean_reference("<lip-smack> अच्छा </lip-smack>").text == "अच्छा"
