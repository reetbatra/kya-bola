"""AI4Bharat IndicConformer, run locally.

This is the honest open-source baseline: MIT licensed, built specifically for
Indian languages, covering all 22 scheduled ones, and free to run. It is a more
useful comparison than a generalist API, because it answers "how much of this
is the model versus how much is the task" rather than "how does a system built
for English cope with Indic audio".

Runs on the local machine, so there is no rate limit and no quota to exhaust.
"""

from __future__ import annotations

import os
import time

from harness.providers.base import Provider, Transcription

MODEL_ID = "ai4bharat/indic-conformer-600m-multilingual"

# IndicConformer takes bare ISO-639-1 codes, not the BCP-47 Sarvam uses.
BCP47_TO_ISO: dict[str, str] = {
    "hi-IN": "hi", "bn-IN": "bn", "ta-IN": "ta", "te-IN": "te",
    "kn-IN": "kn", "ml-IN": "ml", "mr-IN": "mr", "gu-IN": "gu",
    "pa-IN": "pa", "od-IN": "or", "as-IN": "as", "ur-IN": "ur",
    "ne-IN": "ne", "sa-IN": "sa", "mai-IN": "mai", "kok-IN": "kok",
    "ks-IN": "ks", "mni-IN": "mni", "sat-IN": "sat", "sd-IN": "sd",
    "brx-IN": "brx", "doi-IN": "doi",
}


class IndicConformerProvider(Provider):
    supported_codes = frozenset(BCP47_TO_ISO)

    def __init__(self, decoding: str = "ctc", device: str | None = None):
        self.name = f"indicconformer:{decoding}"
        self.decoding = decoding
        self._device = device
        self._model = None

    def _load(self):
        if self._model is not None:
            return self._model
        import torch
        from transformers import AutoModel

        device = self._device or ("mps" if torch.backends.mps.is_available() else "cpu")
        # The model repo is gated, same as the Vaani datasets.
        model = AutoModel.from_pretrained(
            MODEL_ID, trust_remote_code=True, token=os.environ.get("HF_TOKEN")
        )
        model = model.to(device).eval()
        self._device = device
        self._model = model
        return model

    def transcribe(self, wav_path: str, language_code: str) -> Transcription:
        iso = BCP47_TO_ISO.get(language_code)
        if iso is None:
            # No auto-detect: the model requires an explicit language. For the
            # 45 languages it does not cover, that refusal IS the result, and
            # it is exactly what a developer building for those speakers hits.
            return Transcription(
                text=None,
                error=f"unsupported language {language_code}",
                failure_kind="refusal",
            )

        import torch
        import torchaudio

        started = time.monotonic()
        try:
            model = self._load()
            wav, sr = torchaudio.load(wav_path)
            if sr != 16_000:
                wav = torchaudio.functional.resample(wav, sr, 16_000)
            if wav.shape[0] > 1:
                wav = wav.mean(dim=0, keepdim=True)
            with torch.no_grad():
                text = model(wav.to(self._device), iso, self.decoding)
        except Exception as exc:  # noqa: BLE001
            # A local crash is infrastructure, not the model declining the clip.
            return Transcription(
                text=None,
                error=f"{type(exc).__name__}: {exc}",
                failure_kind="infrastructure",
                latency_s=time.monotonic() - started,
            )

        if isinstance(text, (list, tuple)):
            text = text[0] if text else ""
        return Transcription(
            text=str(text).strip() or None,
            detected_language=iso,
            latency_s=time.monotonic() - started,
        )
