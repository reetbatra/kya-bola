"""Sarvam AI speech-to-text provider.

Uses the synchronous REST endpoint. The batch API exists but is priced
identically (Rs 30/hour for real-time, streaming and batch alike, confirmed on
sarvam.ai/api-pricing) and caps at 20 files per job, so it buys nothing here.

Vaani clips average about 5 seconds against the endpoint's 30-second ceiling,
so no chunking is needed.
"""

from __future__ import annotations

import os
import time

import requests

from harness.languages import SARVAM_CODES
from harness.providers.base import (
    Provider,
    ProviderQuotaError,
    RateLimiter,
    Transcription,
)

ENDPOINT = "https://api.sarvam.ai/speech-to-text"

# Sarvam Starter: 60 req/min, account-wide. Run under it.
DEFAULT_RPM = 50
MAX_RETRIES = 5


class SarvamProvider(Provider):
    supported_codes = SARVAM_CODES

    def __init__(
        self,
        model: str = "saaras:v3",
        api_key: str | None = None,
        rpm: int = DEFAULT_RPM,
        timeout: int = 60,
    ):
        self.model = model
        self.name = f"sarvam:{model}"
        self.timeout = timeout
        self.limiter = RateLimiter(rpm)
        self.api_key = api_key or os.environ.get("SARVAM_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "SARVAM_API_KEY is not set. Put it in .env (never in source) "
                "and load it with python-dotenv."
            )

    def transcribe(self, wav_path: str, language_code: str) -> Transcription:
        data = {"model": self.model}
        # `mode` is a saaras:v3 parameter; v4 rejects it.
        if self.model.startswith("saaras:v3"):
            data["mode"] = "transcribe"
        # Unsupported languages go through auto-detect, and what the API claims
        # the language is gets recorded as a result in its own right.
        data["language_code"] = language_code if language_code in SARVAM_CODES else "unknown"

        last_error = None
        for attempt in range(MAX_RETRIES):
            self.limiter.acquire()
            started = time.monotonic()
            try:
                with open(wav_path, "rb") as fh:
                    response = requests.post(
                        ENDPOINT,
                        headers={"api-subscription-key": self.api_key},
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
                # Respect Retry-After when the server sends one.
                delay = float(response.headers.get("Retry-After", 2**attempt))
                last_error = "429 rate limited"
                time.sleep(delay)
                continue

            if response.status_code >= 500:
                last_error = f"{response.status_code}: {response.text[:200]}"
                time.sleep(2**attempt)
                continue

            if response.status_code >= 400:
                # 4xx other than 429 is a real refusal (e.g. unsupported
                # language). Do not retry -- record it as the result.
                body = response.text[:300]
                if response.status_code in (401, 402, 403) or "quota" in body.lower():
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
                text=payload.get("transcript"),
                detected_language=payload.get("language_code"),
                language_probability=payload.get("language_probability"),
                latency_s=latency,
            )

        return Transcription(
            text=None,
            error=f"exhausted retries: {last_error}",
            failure_kind="infrastructure",
        )
