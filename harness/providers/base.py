"""Provider interface and shared rate limiting.

Every ASR backend implements the same three-method surface so the runner can
treat a paid API and a local model identically.
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass


class ProviderQuotaError(RuntimeError):
    """The account is out of credits. Stop the run; do not score the rest."""


@dataclass(frozen=True)
class Transcription:
    """One provider's answer for one clip.

    `text` is None for two very different reasons, and conflating them would
    corrupt the benchmark:

    * `failure_kind="refusal"` -- the model was asked and produced nothing, or
      the API rejected the request on its merits (an unsupported language, say).
      That is a real failure by the provider and scores 1.0.
    * `failure_kind="infrastructure"` -- quota exhausted, auth rejected, network
      dropped. The model never got a fair shot, so the clip is excluded rather
      than counted against it.
    """
    text: str | None
    detected_language: str | None = None
    language_probability: float | None = None
    error: str | None = None
    latency_s: float | None = None
    failure_kind: str | None = None  # None | "refusal" | "infrastructure"


class RateLimiter:
    """Token bucket, thread-safe.

    Sarvam's Starter tier allows 60 requests/minute and the limit is
    account-wide across all keys, not per-key. We run at 50 to leave headroom
    for anything else using the account.
    """

    def __init__(self, per_minute: int):
        self.interval = 60.0 / per_minute
        self._lock = threading.Lock()
        self._next_at = 0.0

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            wait = self._next_at - now
            if wait > 0:
                time.sleep(wait)
                now = time.monotonic()
            self._next_at = now + self.interval


class Provider(ABC):
    """Base class for every ASR backend."""

    name: str
    #: Language codes this provider documents support for. Empty means the
    #: provider accepts anything (local models, auto-detect-only APIs).
    supported_codes: frozenset[str] = frozenset()

    @abstractmethod
    def transcribe(self, wav_path: str, language_code: str) -> Transcription:
        """Transcribe one audio file. Must not raise for ordinary API errors."""

    def health_check(self, wav_path: str, language_code: str) -> Transcription:
        """Prove the provider works on one known-good clip before a bulk run."""
        return self.transcribe(wav_path, language_code)

    def __repr__(self) -> str:
        return f"<{type(self).__name__} name={self.name!r}>"
