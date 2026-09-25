"""Speech-to-text backend for Say It (local dictation and cloud).

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

_log = logging.getLogger("sayit")

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
}


def _filter_hallucination(text: str) -> str:
    """Filter out common Whisper silence hallucinations and prompt echoes."""
    cleaned = " ".join(text.split())
    norm = cleaned.lower().strip(" .!?,;:")
    if not norm or norm in _HALLUCINATIONS:
        return ""
    # Wipe an all-credit line ("subtitles by ..."), but not a real sentence
    # that merely opens with those words.
    if len(norm.split()) < 6 and any(
        norm.startswith(h) for h in ("subtitles by", "transcript by", "translated by")
    ):
        return ""

    # Excise the hallucination phrase in place; keep any surrounding real text
    # (no trailing .* — that ate the rest of the sentence).
    for pat in (
        r"(?i)\s*(?:thanks?\s+(?:you\s+)?for\s+watching|please\s+subscribe|subtitles\s+by\b)",
        r"(?i)\s*(?:tch|tech|text)\s+terms?\s+(?:are|is|available|not\s+needed)\b",
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
            try:
                self._model = WhisperModel(
                    self.model,
                    device=device,
                    compute_type=compute_type,
                    local_files_only=True,
                )
            except Exception as e:
                # A genuine CUDA-runtime failure must reach transcribe() UNWRAPPED so
                # its _is_cuda_error() check triggers the one-shot CPU int8 fallback
                # (the build ships without cuBLAS/cuDNN and relies on that fallback).
                # Only wrap a real "not available locally" failure with the friendly
                # message — _build_stt already gate-checks is_downloaded, so that path
                # is the rare cache-mismatch / partial-download case.
                if _is_cuda_error(e):
                    raise
                raise RuntimeError(
                    f"speech model {self.model!r} isn't available locally for "
                    f"{device}/{compute_type}. Download it from the Models panel "
                    f"first, then retry (or check the GPU/compute setup)."
                ) from e
            _log.info("sayit stt: loaded %s on %s/%s", self.model, device, compute_type)
        return self._model

    def _compute(self, pcm: np.ndarray, task: str, language: str | None, prompt: str | None = None) -> str:
        model = self._get_model()
        segments, _info = model.transcribe(
            pcm.astype(np.float32, copy=False),
            task=task,
            language=language,
            initial_prompt=prompt,
            beam_size=1,  # greedy search: 2-3x faster for low-latency dictation
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
                _log.warning("sayit stt: CUDA unavailable (%s); falling back to CPU int8", e)
                self._forced_cpu = True
                self._model = None
                if "large" in self.model:
                    _log.warning("sayit stt: using 'base' model on CPU to prevent excessive latency")
                    self.model = "base"
                return self._compute(pcm, task, language, prompt=prompt)
            raise


GROQ_TRANSCRIPTION_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_AVAILABLE_MODELS = ("whisper-large-v3-turbo", "whisper-large-v3")


class GroqWhisperBackend:
    """Cloud STT using Groq's Whisper API.
    
    Converts 16kHz float32 mono PCM to 16-bit WAV in memory and posts to
    https://api.groq.com/openai/v1/audio/transcriptions. Uses persistent HTTP
    connections and text response format for sub-350ms transcription.
    """

    def __init__(
        self,
        model: str = "whisper-large-v3-turbo",
        api_key: str | None = None,
    ):
        self.model = model
        self.api_key = api_key
        self._client = None
        self._session = None

    def _get_client(self):
        if self._client is None:
            try:
                import httpx
                # Keep-alive connection pooling eliminates 200-400ms DNS/TLS handshake overhead
                self._client = httpx.Client(
                    timeout=15.0,
                    limits=httpx.Limits(max_keepalive_connections=5, keepalive_expiry=60.0),
                    transport=httpx.HTTPTransport(retries=2),
                )
            except Exception:
                self._client = False
        return self._client if self._client is not False else None

    def _get_session(self):
        if self._session is None:
            try:
                import requests
                self._session = requests.Session()
            except Exception:
                self._session = False
        return self._session if self._session is not False else None

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

        # response_format="text" is 2-3x faster on Groq than "json"
        data = {
            "model": self.model,
            "response_format": "text",
            "temperature": "0.0",
        }
        if lang_in and lang_in != "auto":
            data["language"] = lang_in
        if prompt and prompt.strip():
            data["prompt"] = prompt.strip()

        endpoint = GROQ_TRANSCRIPTION_URL
        if lang_out == "en" and lang_in and lang_in != "en" and lang_in != "auto":
            endpoint = "https://api.groq.com/openai/v1/audio/translations"

        headers = {"Authorization": f"Bearer {key}"}
        client = self._get_client()
        resp_text = None

        if client is not None:
            try:
                r = client.post(
                    endpoint,
                    headers=headers,
                    files={"file": ("audio.wav", wav_bytes, "audio/wav")},
                    data=data,
                )
                if r.status_code == 200:
                    resp_text = r.text
                elif r.status_code in (401, 403, 429):
                    raise RuntimeError(f"Groq STT HTTP {r.status_code}: {r.text[:200]}")
            except Exception as err:
                _log.warning("httpx Groq STT error (%s); trying requests fallback", err)

        # Secondary fallback: requests session
        if resp_text is None:
            sess = self._get_session()
            post_fn = sess.post if sess else None
            if post_fn is None:
                import requests
                post_fn = requests.post
            resp = post_fn(
                endpoint,
                headers=headers,
                files={"file": ("audio.wav", wav_bytes, "audio/wav")},
                data=data,
                timeout=15.0,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"Groq STT HTTP {resp.status_code}: {resp.text[:200]}")
            resp_text = resp.text

        text = (resp_text or "").strip()
        return _filter_hallucination(text)


class NullBackend:
    """No speech engine selected -> transcribe() always raises a friendly error.

    Loads no model, touches no GPU, makes no network call. Wired by
    SayItApp._build_stt when stt_provider is 'none'/unknown, or when the chosen
    provider isn't usable (no Groq key, or the local model isn't downloaded)."""

    def transcribe(self, *args, **kwargs) -> str:
        raise RuntimeError(
            "No speech engine configured — choose Cloud (Groq) or On-Device in Transcription settings."
        )

