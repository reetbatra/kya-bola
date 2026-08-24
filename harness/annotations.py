"""Strip Vaani transcriber annotations from reference text.

Vaani transcripts are not plain text. They carry a transcription convention
that, scored raw, invents errors no ASR system committed. Measured over 750
transcripts from Hindi, Kannada and Garo:

  <noise> ... </noise>   56.3%  paired event tags that WRAP real speech
  {side}                 35.5%  Latin gloss of the word just written natively
  [unintelligible]       10.1%  non-speech events and annotator notes
  --                     15.3%  truncation marker

The paired tags are the dangerous one. In Garo, `<noise> ia nokni rongde ...
</noise>` puts the entire utterance inside the tags, so removing tag-and-content
would delete the reference for more than half the clips and score every model
against an empty string.

The braces are the opposite case. `साइड {side}` is one spoken word written
twice, once in Devanagari and once as a Latin gloss, so the brace group must go
entirely or the reference gains a word the speaker never said twice.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Paired or standalone XML-ish event tags. The vocabulary is open (noise, pause,
# static, static_noise, talking, ...), so match structurally rather than listing.
_TAG = re.compile(r"</?[A-Za-z][A-Za-z0-9_]{0,30}>")

# Square-bracket annotator notes: [unintelligible], [inhaling], [horn].
# These describe audio, they are not spoken words. Remove group and content.
_EVENT = re.compile(r"\[[^\]]{0,60}\]")

# Curly-brace Latin gloss of the preceding native-script word.
_GLOSS = re.compile(r"\{[^}]{0,60}\}")

# Truncation marker for a word the speaker cut off.
_TRUNCATED = re.compile(r"--+")

# Stray apostrophe runs left by the transcription tooling ('' and '''').
_QUOTE_RUN = re.compile(r"'{2,}")

# References the human transcriber could not make out. The audio is real but the
# ground truth is not trustworthy, so these are flagged and excluded by default
# rather than counted as model errors.
_UNCERTAIN = re.compile(r"\[(unintelligible|inaudible)\]", re.IGNORECASE)

_WS = re.compile(r"\s+")


@dataclass(frozen=True)
class CleanedReference:
    text: str
    uncertain: bool       # transcriber marked part of it unintelligible
    empty_after_clean: bool
    removed: dict[str, int]

    @property
    def usable(self) -> bool:
        return not self.empty_after_clean and not self.uncertain


def clean_reference(raw: str | None) -> CleanedReference:
    """Remove transcriber annotations, keeping the words actually spoken."""
    if not raw:
        return CleanedReference("", uncertain=False, empty_after_clean=True, removed={})

    removed = {
        "tags": len(_TAG.findall(raw)),
        "events": len(_EVENT.findall(raw)),
        "glosses": len(_GLOSS.findall(raw)),
        "truncations": len(_TRUNCATED.findall(raw)),
    }
    uncertain = bool(_UNCERTAIN.search(raw))

    text = raw
    # Order matters: drop bracket/brace groups before tags, so a tag nested
    # inside a note cannot leave an orphan fragment behind.
    text = _EVENT.sub(" ", text)
    text = _GLOSS.sub(" ", text)
    text = _TAG.sub(" ", text)          # tags only, inner speech survives
    text = _TRUNCATED.sub(" ", text)
    text = _QUOTE_RUN.sub(" ", text)
    text = _WS.sub(" ", text).strip()

    return CleanedReference(
        text=text,
        uncertain=uncertain,
        empty_after_clean=not text,
        removed=removed,
    )
