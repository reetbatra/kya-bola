"""Indic-aware text normalization for ASR scoring.

The single most important rule in this file: we never strip Unicode category M.

The widely-copied Whisper `BasicTextNormalizer` removes every character whose
Unicode category starts with M, S or P. In every Brahmic script the vowel signs
(matras) and the virama/halant are category M, so that normalizer silently
deletes the vowels from Indic text. It makes WER look better while destroying
the thing being compared -- a documented case took Malayalam from 16.6% to
7.69% purely through this corruption.

We strip P and S. We keep M. See tests/test_normalize.py, which pins this.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from indicnlp.normalize.indic_normalize import IndicNormalizerFactory

# Unicode block starts for the scripts present in the Vaani corpus. Order
# matters only for readability; lookup is by explicit range test below.
_SCRIPT_RANGES: list[tuple[int, int, str]] = [
    (0x0900, 0x097F, "Devanagari"),
    (0x0980, 0x09FF, "Bengali"),
    (0x0A00, 0x0A7F, "Gurmukhi"),
    (0x0A80, 0x0AFF, "Gujarati"),
    (0x0B00, 0x0B7F, "Oriya"),
    (0x0B80, 0x0BFF, "Tamil"),
    (0x0C00, 0x0C7F, "Telugu"),
    (0x0C80, 0x0CFF, "Kannada"),
    (0x0D00, 0x0D7F, "Malayalam"),
    (0x0600, 0x06FF, "Arabic"),
    (0x0750, 0x077F, "Arabic"),
    (0xFB50, 0xFDFF, "Arabic"),
    (0x11100, 0x1114F, "Chakma"),
    (0xABC0, 0xABFF, "MeeteiMayek"),
    (0x1C50, 0x1C7F, "OlChiki"),
    (0x0041, 0x024F, "Latin"),
]

# indic-nlp normalizer codes, keyed by detected script. Scripts absent from
# this map get NFC plus the shared cleanup only -- correct behaviour, not a
# silent downgrade, and `normalize()` reports which path it took.
_SCRIPT_TO_INDICNLP: dict[str, str] = {
    "Devanagari": "hi",
    "Bengali": "bn",
    "Gurmukhi": "pa",
    "Gujarati": "gu",
    "Oriya": "or",
    "Tamil": "ta",
    "Telugu": "te",
    "Kannada": "kn",
    "Malayalam": "ml",
}

# Native digit blocks -> ASCII. A model may emit "5" where the reference has
# "५"; those are the same token and should not count as an error.
_DIGIT_BASES = [0x0966, 0x09E6, 0x0A66, 0x0AE6, 0x0B66, 0x0BE6, 0x0C66, 0x0CE6, 0x0D66, 0x0660, 0x06F0]
_DIGIT_MAP = {base + i: str(i) for base in _DIGIT_BASES for i in range(10)}

_WS = re.compile(r"\s+")


def detect_script(text: str) -> str:
    """Return the dominant script of `text`, ignoring spaces and digits."""
    counts: dict[str, int] = {}
    for ch in text:
        cp = ord(ch)
        if ch.isspace() or ch.isdigit():
            continue
        for lo, hi, name in _SCRIPT_RANGES:
            if lo <= cp <= hi:
                counts[name] = counts.get(name, 0) + 1
                break
    if not counts:
        return "Unknown"
    return max(counts.items(), key=lambda kv: kv[1])[0]


@lru_cache(maxsize=32)
def _normalizer(code: str):
    return IndicNormalizerFactory().get_normalizer(code)


def strip_punct_and_symbols(text: str) -> str:
    """Drop Unicode P and S characters. Marks (M) are deliberately preserved."""
    out = []
    for ch in text:
        cat = unicodedata.category(ch)
        if cat[0] in ("P", "S"):
            out.append(" ")
        else:
            out.append(ch)
    return "".join(out)


def normalize(text: str, script: str | None = None) -> tuple[str, str]:
    """Normalize `text` for scoring.

    Returns (normalized_text, script_used). Pass `script` to force a script,
    otherwise it is detected from the text itself -- which is what we want for
    the ~45 corpus languages that have no declared script and no ISO mapping.
    """
    if text is None:
        return "", "Unknown"

    script = script or detect_script(text)

    # NFC first: canonical composition, so identical rendered characters that
    # differ only in codepoint ordering compare equal.
    text = unicodedata.normalize("NFC", text)

    code = _SCRIPT_TO_INDICNLP.get(script)
    if code is not None:
        # Script-aware pass: collapses multi-codepoint variants of the same
        # character and fixes common Latin-keyboard typing artefacts.
        text = _normalizer(code).normalize(text)

    text = text.translate(_DIGIT_MAP)
    text = strip_punct_and_symbols(text)

    if script in ("Latin", "Unknown"):
        text = text.casefold()

    text = _WS.sub(" ", text).strip()
    return text, script
