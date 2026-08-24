"""Registry of the 64 language configs in ARTPARK-IISc/Vaani-transcription-part.

Two facts drive the whole project and live here:

1. Sarvam's STT documents 23 language codes. 19 of them appear in this corpus.
   The other 45 corpus languages are supported by no commercial ASR API at all.
2. WER over-punishes agglutinative languages, where one token carries what
   English would spread across a clause. For those we report CER as primary.

Sarvam codes verified against
https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/how-to/specify-language-codes
Note Odia is `od-IN`, not the ISO-conventional `or-IN`.
"""

from __future__ import annotations

from dataclasses import dataclass

# Every code Sarvam's STT accepts, verified from the docs page above.
SARVAM_CODES: frozenset[str] = frozenset(
    """as-IN bn-IN brx-IN doi-IN en-IN gu-IN hi-IN kn-IN kok-IN ks-IN mai-IN
       ml-IN mni-IN mr-IN ne-IN od-IN pa-IN sa-IN sat-IN sd-IN ta-IN te-IN
       ur-IN""".split()
)

# Dravidian languages: heavily agglutinative, so a single wrong morpheme inside
# one long token marks the whole word wrong. CER is the honest primary metric.
_CER_PRIMARY = {
    "Tamil", "Telugu", "Kannada", "Malayalam", "Tulu", "Bearybashe", "Gondi", "Kurukh",
}


@dataclass(frozen=True)
class Language:
    name: str            # Vaani config name, e.g. "Hindi"
    clips: int           # transcribed clips available in the corpus
    sarvam_code: str | None  # BCP-47 code Sarvam accepts, or None if unsupported

    @property
    def supported(self) -> bool:
        return self.sarvam_code is not None

    @property
    def primary_metric(self) -> str:
        return "cer" if self.name in _CER_PRIMARY else "wer"

    @property
    def request_code(self) -> str:
        """What to send as `language_code`.

        For unsupported languages we send "unknown" and let the API guess. What
        it guesses is itself a result worth recording: when Saaras is handed
        Garo, what does it claim the language is?
        """
        return self.sarvam_code or "unknown"


# (name, transcribed clip count, sarvam code or None). Counts read from the HF
# dataset_info for ARTPARK-IISc/Vaani-transcription-part on 2026-08-24.
_RAW: list[tuple[str, int, str | None]] = [
    ("Hindi", 636_655, "hi-IN"),
    ("Bengali", 113_617, "bn-IN"),
    ("Telugu", 103_634, "te-IN"),
    ("Kannada", 92_622, "kn-IN"),
    ("Marathi", 42_778, "mr-IN"),
    ("Garo", 41_834, None),
    ("Chakma", 41_140, None),
    ("Odia", 31_073, "od-IN"),
    ("Nepali", 29_389, "ne-IN"),
    ("Malayalam", 29_225, "ml-IN"),
    ("Assamese", 26_917, "as-IN"),
    ("Tamil", 24_441, "ta-IN"),
    ("English", 18_381, "en-IN"),
    ("Nagamese", 16_111, None),
    ("Bhojpuri", 14_134, None),
    ("Punjabi", 12_863, "pa-IN"),
    ("Mizo", 12_258, None),
    ("Chhattisgarhi", 11_773, None),
    ("Gujarati", 11_278, "gu-IN"),
    ("Wancho", 11_122, None),
    ("Maithili", 10_690, "mai-IN"),
    ("Rajasthani", 8_093, None),
    ("Garhwali", 5_894, None),
    ("Marwari", 4_787, None),
    ("Magadhi", 3_616, None),
    ("Kokborok", 3_064, None),
    ("Magahi", 2_837, None),
    ("Khortha", 2_633, None),
    ("Bajjika", 2_310, None),
    ("Konkani", 2_221, "kok-IN"),
    ("Tulu", 2_059, None),
    ("Angika", 1_830, None),
    ("Urdu", 1_422, "ur-IN"),
    ("Kumaoni", 1_142, None),
    ("IduMishmi", 1_116, None),
    ("Halbi", 1_070, None),
    ("Sumi", 944, None),
    ("Khariboli", 718, None),
    ("Sadri", 685, None),
    ("Malvani", 670, None),
    ("Karbi", 607, None),
    ("Surgujia", 529, None),
    ("Bundeli", 447, None),
    ("Rengma", 375, None),
    ("Chakhesang", 293, None),
    ("Ao", 289, None),
    ("Kashmiri", 282, "ks-IN"),
    ("Gondi", 272, None),
    ("Manipuri", 253, "mni-IN"),
    ("Rongmei", 198, None),
    ("Surjapuri", 197, None),
    ("Awadhi", 187, None),
    ("Haryanvi", 165, None),
    ("Sambalpuri", 154, None),
    ("Kurukh", 135, None),
    ("Bearybashe", 130, None),
    ("Bhili", 116, None),
    ("Angami", 111, None),
    ("Thethi", 106, None),
    ("Tagin", 93, None),
    ("Jaipuri", 87, None),
    ("Nyishi", 82, None),
    ("Santali", 79, "sat-IN"),
    ("Nagpuri", 76, None),
]

LANGUAGES: dict[str, Language] = {n: Language(n, c, s) for n, c, s in _RAW}

SUPPORTED = [lang for lang in LANGUAGES.values() if lang.supported]
UNSUPPORTED = [lang for lang in LANGUAGES.values() if not lang.supported]


def config_name(name: str) -> str:
    """HF builder-config name for a language.

    The dataset card's `dataset_info` lists these as "audio/Hindi", but that is
    the data path; the builder config is the bare language name.
    """
    return name


def get(name: str) -> Language:
    try:
        return LANGUAGES[name]
    except KeyError:
        raise KeyError(
            f"{name!r} is not a Vaani language config. "
            f"Known: {', '.join(sorted(LANGUAGES))}"
        ) from None
