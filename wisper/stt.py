"""Speech-to-text backend for Wisper (local dictation).

faster-whisper (CTranslate2) running Whisper large-v3-turbo on CUDA/fp16 by
default. Batch transcription of a whole utterance after the hotkey stops —
no streaming. The heavy `faster_whisper` import and model load are deferred to
the first real `transcribe` call, so constructing the backend is cheap and
needs no GPU (lets the orchestrator import/wire this on any machine).
"""

from __future__ import annotations

import logging
import re

import numpy as np

_log = logging.getLogger("wisper")

# ponytail: "approximately zero" audio floor. float32 mic input sits in ~[-1,1];
# genuine silence/DC is well under this. Bump if a noisy capture chain trips it.
_SILENCE_THRESHOLD = 1e-4
_MIN_AUDIO_SAMPLES = int(16000 * 0.4)  # 0.4s minimum speech threshold

_HALLUCINATIONS = {
    "thank you",
    "thank you.",
    "thank you!",
    "thank you very much",
    "thank you very much.",
    "thank you so much",
    "thank you so much.",
    "thanks for watching",
    "thanks for watching.",
    "thanks for watching!",
    "thank you for watching",
    "thank you for watching.",
    "please subscribe",
    "please subscribe.",
    "subtitles by",
    "subtitles by the amara.org community",
    "you",
    "bye",
    "bye.",
    "silence",
    "music",
}


def _filter_hallucination(text: str) -> str:
    """Filter out common Whisper silence hallucinations and prompt echoes."""
    cleaned = " ".join(text.split())
    norm = cleaned.lower().strip(" .!?,;:")
    if not norm or norm in _HALLUCINATIONS:
        return ""
    if any(norm.startswith(h) for h in ("subtitles by", "transcript by", "translated by")):
        return ""

    # Strip trailing hallucination sentences (e.g. "... Thanks for watching.")
    for pat in (
        r"(?i)\s*(?:thanks?\s+(?:you\s+)?for\s+watching|please\s+subscribe|subtitles\s+by\b).*$",
        r"(?i)\s*(?:tch|tech|text)\s+terms?\s+(?:are|is|available|not\s+needed)\b.*$",
    ):
        cleaned = re.sub(pat, "", cleaned).strip()

    return cleaned


def _is_cuda_error(exc: Exception) -> bool:
    """True if `exc` looks like a missing/broken CUDA runtime (cuBLAS/cuDNN/etc)."""
    msg = str(exc).lower()
    return any(
        t in msg
        for t in ("cublas", "cudnn", "cuda", "is not found", "cannot be loaded")
    )


def _resolve_task(lang_in: str | None, lang_out: str) -> tuple[str, str | None]:
    """Map (source, target) languages to a faster-whisper (task, language) pair.

    Whisper's only translation direction is X->English. So translate when the
    target is English and the source is a known non-English language; otherwise
    transcribe in `lang_in` (None => let Whisper auto-detect).
    """
    if lang_out == "en" and lang_in is not None and lang_in != "en" and lang_in != "auto":
        return ("translate", lang_in)
    return ("transcribe", None if lang_in == "auto" else lang_in)


class FasterWhisperBackend:
    def __init__(
        self,
        model: str = "large-v3-turbo",
        device: str = "cuda",
        compute_type: str = "float16",
    ):
        self.model = model
        self.device = device
        self.compute_type = compute_type
        self._model = None  # lazy: built on first transcribe
        # ponytail: sticky CPU fallback for the process; a GPU that appears
        # mid-run isn't re-probed — restart to re-detect.
        self._forced_cpu = False

    def _target(self) -> tuple[str, str]:
        """Resolve the (device, compute_type) to actually load with.

        CPU only supports int8 here (float16 is GPU-only and would error), so
        any CPU path — requested or fallen-back-to — is forced to int8.
        """
        if self._forced_cpu or self.device == "cpu":
            return ("cpu", "int8")
        return (self.device, self.compute_type)

    def _get_model(self):
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as e:
                raise RuntimeError(
                    "faster-whisper is not installed; run "
                    "`pip install faster-whisper` to enable transcription"
                ) from e
            device, compute_type = self._target()
            self._model = WhisperModel(self.model, device=device, compute_type=compute_type)
            _log.info("wisper stt: loaded %s on %s/%s", self.model, device, compute_type)
        return self._model

    def _compute(self, pcm: np.ndarray, task: str, language: str | None, prompt: str | None = None) -> str:
        model = self._get_model()
        segments, _info = model.transcribe(
            pcm.astype(np.float32, copy=False),
            task=task,
            language=language,
            initial_prompt=prompt,
            beam_size=5,
            vad_filter=True,  # built-in Silero: strips silence, kills hallucinations
        )
        text = " ".join(seg.text for seg in segments)
        return _filter_hallucination(text)

    def transcribe(
        self,
        pcm: np.ndarray,
        lang_in: str | None = "en",
        lang_out: str = "en",
        prompt: str | None = None,
    ) -> str:
        """Transcribe float32 mono @16kHz PCM (~[-1,1]) to cleaned text.

        Empty, near-silent, or very short (<0.4s) audio returns "" without loading the model.
        Common hallucinations (e.g. 'Thank you.') are filtered to "".
        Falls back from a broken CUDA runtime to CPU int8 once, then sticks.
        """
        if pcm is None or pcm.size < _MIN_AUDIO_SAMPLES or float(np.max(np.abs(pcm))) < _SILENCE_THRESHOLD:
            return ""

        task, language = _resolve_task(lang_in, lang_out)
        try:
            return self._compute(pcm, task, language, prompt=prompt)
        except Exception as e:
            # Only fall back when we were on a GPU path and the failure looks
            # like a missing/broken CUDA runtime. Rebuild on CPU and retry once.
            if not self._forced_cpu and self.device != "cpu" and _is_cuda_error(e):
                _log.warning("wisper stt: CUDA unavailable (%s); falling back to CPU int8", e)
                self._forced_cpu = True
                self._model = None
                if "large" in self.model:
                    _log.warning("wisper stt: using 'base' model on CPU to prevent excessive latency")
                    self.model = "base"
                return self._compute(pcm, task, language, prompt=prompt)
            raise


GROQ_TRANSCRIPTION_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_AVAILABLE_MODELS = ("whisper-large-v3-turbo", "whisper-large-v3")


class GroqWhisperBackend:
    """Cloud STT using Groq's Whisper API.
    
    Converts 16kHz float32 mono PCM to 16-bit WAV in memory and posts to
    https://api.groq.com/openai/v1/audio/transcriptions. Typically finishes in 300-500ms.
    Uses httpx with connection retries, falling back to requests.
    """

    def __init__(
        self,
        model: str = "whisper-large-v3-turbo",
        api_key: str | None = None,
    ):
        self.model = model
        self.api_key = api_key

    def transcribe(
        self,
        pcm: np.ndarray,
        lang_in: str | None = "en",
        lang_out: str = "en",
        prompt: str | None = None,
    ) -> str:
        import io
        import os
        import wave

        if pcm is None or pcm.size < _MIN_AUDIO_SAMPLES or float(np.max(np.abs(pcm))) < _SILENCE_THRESHOLD:
            return ""

        key = (self.api_key or os.environ.get("GROQ_API_KEY", "")).strip()
        if not key:
            raise RuntimeError("GROQ_API_KEY not configured in .env or environment")

        pcm_clipped = np.clip(pcm, -1.0, 1.0)
        pcm_int16 = (pcm_clipped * 32767).astype(np.int16)

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(pcm_int16.tobytes())
        wav_bytes = buf.getvalue()

        data = {
            "model": self.model,
            "response_format": "json",
            "temperature": "0.0",
        }
        if lang_in and lang_in != "auto":
            data["language"] = lang_in
        if prompt:
            data["prompt"] = prompt

        endpoint = GROQ_TRANSCRIPTION_URL
        if lang_out == "en" and lang_in and lang_in != "en" and lang_in != "auto":
            endpoint = "https://api.groq.com/openai/v1/audio/translations"

        resp = None
        # Primary: httpx with automatic retries for robust TLS
        try:
            import httpx
            with httpx.Client(timeout=30.0, transport=httpx.HTTPTransport(retries=3)) as client:
                r = client.post(
                    endpoint,
                    headers={"Authorization": f"Bearer {key}"},
                    files={"file": ("audio.wav", wav_bytes, "audio/wav")},
                    data=data,
                )
                if r.status_code == 200:
                    text = (r.json().get("text") or "").strip()
                    return _filter_hallucination(text)
                resp = r
        except Exception as err:
            _log.warning("httpx Groq STT connection error (%s); trying requests fallback", err)

        # Secondary fallback: requests
        if resp is None:
            import requests
            resp = requests.post(
                endpoint,
                headers={"Authorization": f"Bearer {key}"},
                files={"file": ("audio.wav", wav_bytes, "audio/wav")},
                data=data,
                timeout=30.0,
            )

        if resp.status_code != 200:
            raise RuntimeError(f"Groq STT HTTP {resp.status_code}: {resp.text[:200]}")
        text = (resp.json().get("text") or "").strip()
        return _filter_hallucination(text)


class ResilientGroqSTTBackend:
    """Uses GroqWhisperBackend by default, seamlessly falling back to local
    FasterWhisperBackend if network or Groq fails so dictation never drops."""

    def __init__(
        self,
        groq_backend: GroqWhisperBackend,
        fallback_backend: FasterWhisperBackend,
    ):
        self.groq = groq_backend
        self.fallback = fallback_backend

    @property
    def model(self) -> str:
        return self.groq.model

    @model.setter
    def model(self, value: str) -> None:
        self.groq.model = value

    def transcribe(
        self,
        pcm: np.ndarray,
        lang_in: str | None = "en",
        lang_out: str = "en",
        prompt: str | None = None,
    ) -> str:
        try:
            return self.groq.transcribe(pcm, lang_in, lang_out, prompt=prompt)
        except Exception as e:
            _log.warning("Groq STT failed (%s); falling back to local faster-whisper", e)
            return self.fallback.transcribe(pcm, lang_in, lang_out, prompt=prompt)

