"""ElevenLabs Scribe speech-to-text provider.

Scribe is the strongest general-purpose commercial ASR that is not built
specifically for Indian languages, which makes it the useful counterweight to
Sarvam: it says what a well-funded generalist achieves on Indic audio.

Rate limiting here is concurrency-based rather than requests-per-minute. The
API reports live headroom in `current-concurrent-requests` and
`maximum-concurrent-requests` response headers; we run sequentially, which
stays inside every plan tier.
"""

from __future__ import annotations

import os
import time

import requests

from harness.providers.base import (
    Provider,
    ProviderQuotaError,
    RateLimiter,
    Transcription,
)

ENDPOINT = "https://api.elevenlabs.io/v1/speech-to-text"
DEFAULT_MODEL = "scribe_v2"
MAX_RETRIES = 5

# Scribe language codes are ISO-639, not the BCP-47 that Sarvam uses. Only the
# corpus languages Scribe documents support are mapped; everything else goes
# through auto-detect, exactly as with Sarvam, so the two providers face the
# same task on the same clip.
BCP47_TO_ISO639: dict[str, str] = {
    "hi-IN": "hin", "bn-IN": "ben", "ta-IN": "tam", "te-IN": "tel",
    "kn-IN": "kan", "ml-IN": "mal", "mr-IN": "mar", "gu-IN": "guj",
    "pa-IN": "pan", "od-IN": "ori", "as-IN": "asm", "ur-IN": "urd",
    "ne-IN": "nep", "en-IN": "eng", "sa-IN": "san", "mai-IN": "mai",
}


class ElevenLabsProvider(Provider):
    supported_codes = frozenset(BCP47_TO_ISO639)

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        rpm: int = 60,
        timeout: int = 120,
    ):
        self.model = model
        self.name = f"elevenlabs:{model}"
        self.timeout = timeout
        self.limiter = RateLimiter(rpm)
        self.api_key = api_key or os.environ.get("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "ELEVENLABS_API_KEY is not set. Put it in .env, never in source."
            )

    def transcribe(self, wav_path: str, language_code: str) -> Transcription:
        data = {"model_id": self.model}
        iso = BCP47_TO_ISO639.get(language_code)
        if iso:
            data["language_code"] = iso
        # No language hint for the unsupported languages: Scribe auto-detects,
        # and what it detects is recorded as a result.

        last_error = None
        for attempt in range(MAX_RETRIES):
            self.limiter.acquire()
            started = time.monotonic()
            try:
                with open(wav_path, "rb") as fh:
                    response = requests.post(
                        ENDPOINT,
                        headers={"xi-api-key": self.api_key},
                        files={"file": (os.path.basename(wav_path), fh, "audio/wav")},
                        data=data,
                        timeout=self.timeout,
                    )
            except requests.RequestException as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                time.sleep(2**attempt)
                continue

            latency = time.monotonic() - started

            if response.status_code == 429:
                delay = float(response.headers.get("retry-after", 2**attempt))
                last_error = "429 rate limited"
                time.sleep(delay)
                continue

            if response.status_code >= 500:
                last_error = f"{response.status_code}: {response.text[:200]}"
                time.sleep(2**attempt)
                continue

            if response.status_code >= 400:
                body = response.text[:300]
                # Quota and auth failures mean the model never got a fair shot.
                # Raising stops the run instead of silently recording hundreds
                # of clips as model failures.
                if "quota_exceeded" in body or response.status_code == 401:
                    raise ProviderQuotaError(
                        f"{self.name}: {response.status_code} {body}"
                    )
                return Transcription(
                    text=None,
                    error=f"{response.status_code}: {body}",
                    latency_s=latency,
                    failure_kind="refusal",
                )

            payload = response.json()
            return Transcription(
                text=payload.get("text"),
                detected_language=payload.get("language_code"),
                language_probability=payload.get("language_probability"),
                latency_s=latency,
            )

        return Transcription(
            text=None,
            error=f"exhausted retries: {last_error}",
            failure_kind="infrastructure",
        )
