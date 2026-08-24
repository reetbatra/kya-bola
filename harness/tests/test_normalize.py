"""Regression tests for Indic normalization.

The matra tests are the point of this file. If they ever fail, every WER number
the project has published is wrong in the flattering direction.
"""

import unicodedata

import pytest

from harness.normalize import detect_script, normalize, strip_punct_and_symbols

# (label, text, expected_script)
SAMPLES = [
    ("hindi", "नमस्ते दुनिया", "Devanagari"),
    ("bengali", "আমি ভালো আছি", "Bengali"),
    ("tamil", "வணக்கம் நண்பரே", "Tamil"),
    ("malayalam", "എനിക്ക് സുഖമാണ്", "Malayalam"),
    ("telugu", "నేను బాగున్నాను", "Telugu"),
    ("kannada", "ನಾನು ಚೆನ್ನಾಗಿದ್ದೇನೆ", "Kannada"),
    ("gujarati", "હું મજામાં છું", "Gujarati"),
    ("punjabi", "ਮੈਂ ਠੀਕ ਹਾਂ", "Gurmukhi"),
    ("odia", "ମୁଁ ଭଲ ଅଛି", "Oriya"),
    ("urdu", "میں ٹھیک ہوں", "Arabic"),
    ("garo_latin", "Nangko nikenchim ang'a", "Latin"),
]


def _marks(text: str) -> list[str]:
    return [c for c in text if unicodedata.category(c).startswith("M")]


@pytest.mark.parametrize("label,text,expected", SAMPLES)
def test_script_detection(label, text, expected):
    assert detect_script(text) == expected


@pytest.mark.parametrize("label,text,expected", SAMPLES)
def test_marks_survive_normalization(label, text, expected):
    """THE critical invariant: no combining mark may be dropped.

    This is the exact failure mode of Whisper's BasicTextNormalizer, which
    strips Unicode categories M, S and P together. Matras and viramas are M.
    """
    before = _marks(text)
    after = _marks(normalize(text)[0])
    assert len(after) >= len(before), (
        f"{label}: normalization destroyed combining marks "
        f"({len(before)} -> {len(after)}). This is the matra-stripping bug."
    )


def test_virama_and_matra_preserved_explicitly():
    # U+094D DEVANAGARI SIGN VIRAMA, U+0947 DEVANAGARI VOWEL SIGN E
    text = "नमस्ते"
    out, _ = normalize(text)
    assert "्" in out, "virama was stripped"
    assert "े" in out, "matra was stripped"
    assert out == "नमस्ते"


def test_punctuation_and_symbols_are_stripped():
    out, _ = normalize("नमस्ते, दुनिया। ₹100 ~ ok!")
    assert "," not in out and "।" not in out and "₹" not in out and "!" not in out
    # ...but the word content and its marks are untouched.
    assert "नमस्ते" in out and "दुनिया" in out


def test_strip_punct_keeps_marks():
    text = "क्ष, ।"
    kept = strip_punct_and_symbols(text)
    assert "्" in kept
    assert "," not in kept and "।" not in kept


def test_native_digits_map_to_ascii():
    assert normalize("मुझे ५ चाहिए")[0] == normalize("मुझे 5 चाहिए")[0]
    assert normalize("আমার ৭টি")[0] == normalize("আমার 7টি")[0]


def test_whitespace_and_case():
    assert normalize("  Hello   WORLD  ")[0] == "hello world"


def test_nfc_equivalence():
    """Same rendered text, different codepoint order, must compare equal."""
    composed = unicodedata.normalize("NFC", "क़")
    decomposed = unicodedata.normalize("NFD", "क़")
    assert normalize(composed)[0] == normalize(decomposed)[0]


def test_empty_and_none():
    assert normalize("")[0] == ""
    assert normalize(None)[0] == ""


def test_unknown_script_does_not_crash():
    out, script = normalize("𑄌𑄋𑄴𑄟𑄳𑄦")  # Chakma
    assert script == "Chakma"
    assert out
