# 00 — Say It: Overview & Locked Decisions

**Say It** = a fully local, free, open-source alternative to Wispr Flow. Press a global
hotkey → speak → press again → the full, cleaned transcript is pasted at once wherever your
cursor is (VS Code, Notepad, browser, Claude Code terminal, any field). No cloud, no
subscription, no telemetry. Primary target: **Windows 11 + NVIDIA CUDA**. Multilingual
(English + Hindi + Kannada + other Indic), with a choosable output language.

This file is the single source of truth for **what we're building with and why**. Details
live in the numbered docs (see [README](README.md)).

---

## The one key insight

The user experience — "the whole paragraph appears instantly when I stop" — is **not**
streaming word-by-word transcription. It's:

1. Buffer the entire utterance while the hotkey is active.
2. On stop, transcribe the buffered audio **as one batch** on the GPU (fast).
3. Clean it in one pass.
4. Inject it with **one clipboard write + one Ctrl+V** — atomic paste, not simulated typing.

Perceived latency = `transcribe + clean + paste`, targeted **sub-1.5 s for short phrases**
on a warm mid-range NVIDIA GPU. Because there's **no network round-trip**, this can match or
beat cloud tools like Wispr Flow on perceived speed. (An optional background-incremental
path transcribes VAD chunks *while* you speak so only the tail is left on stop — added later
only if long-utterance latency is actually felt.)

---

## Locked stack

| Layer | Decision | Doc |
|-------|----------|-----|
| **Core language** | Python, single process, thread-based (RT audio callback + STT/LLM workers via queues) | [01](01-architecture-and-pipeline.md) |
| **STT engine** | **faster-whisper** (CTranslate2) on CUDA | [02](02-stt-models-and-benchmarks.md) |
| **STT model (default)** | **Whisper large-v3-turbo**, float16 (int8_float16 on ≤8 GB VRAM) | [02](02-stt-models-and-benchmarks.md) |
| **STT fallback / max** | distil-large-v3 or medium (weak GPU/CPU) · large-v3 float16 (max accuracy toggle) | [02](02-stt-models-and-benchmarks.md) |
| **Indic ASR** | large-v3 for Hindi; **AI4Bharat Indic model** (IndicWhisper/IndicConformer) for Kannada | [03](03-multilingual-and-translation.md) |
| **Translate → English** | Whisper built-in `translate` task (English-only output) | [03](03-multilingual-and-translation.md) |
| **Translate → any language** | ASR → **IndicTrans2 distilled 200M** (permissive; Indic↔Indic↔English; beats non-commercial NLLB) | [03](03-multilingual-and-translation.md) |
| **Audio capture** | **sounddevice/PortAudio, WASAPI shared mode, non-communications role**; native rate → resample to 16 kHz mono; Silero VAD | [04](04-audio-capture-no-artifacts.md) |
| **No-ducking mechanism** | Never open the mic under the comms role + guide user to Communications = "Do nothing" | [04](04-audio-capture-no-artifacts.md) |
| **Global hotkey** | `keyboard` lib, **toggle** default (push-to-talk optional); native `RegisterHotKey` fallback | [05](05-text-injection-and-hotkeys.md) |
| **Text injection** | **clipboard-set + Ctrl+V** (save→set→paste→restore); Ctrl+Shift+V in terminals; SendInput-Unicode fallback | [05](05-text-injection-and-hotkeys.md) |
| **Text cleanup (default)** | **Rule-based delete-only** pass — filler dicts + stutter/repeat/false-start collapse + punctuation/caps. Zero latency, zero hallucination, exact wording preserved | [06](06-text-formatting-cleanup.md) |
| **Text cleanup (LLM)** | **Ollama + Qwen2.5-3B (Q4)** for LIGHT/POLISH; Gemma-2-2B fallback | [06](06-text-formatting-cleanup.md) |
| **Storage** | flat **JSON** for config · **SQLite** for last-N history (ring-buffer prune) | [01](01-architecture-and-pipeline.md) |
| **UI (deferred)** | separate process behind a **loopback-socket JSON IPC**; core runs headless | [01](01-architecture-and-pipeline.md) |

---

## The two cleanup modes (exactly as required)

- **LIGHT (default):** remove fillers (um/uh/like/you know + Hindi/Kannada `matlab`/`haan`/…),
  stutters, repeats, false starts. **Keeps your exact words — no paraphrase, no synonym
  swaps.** The rule-based pass guarantees this; the optional LLM light pass is guarded by a
  token-subsequence/overlap check (temp 0.0) that falls back to the rule-based result if the
  model drifts.
- **POLISH (opt-in):** grammar/clarity improvements, faithful to meaning.
- **Optimize/refresh button:** re-runs on the visible text, escalating rule → LLM-light →
  polish; non-destructive with one-step undo.

---

## Multilingual routing (source → output)

| Spoken | Output | Path |
|--------|--------|------|
| English | English | Whisper large-v3 |
| Hindi | Hindi | Whisper large-v3 (IndicWhisper if higher accuracy needed) |
| Kannada | Kannada | AI4Bharat Indic ASR |
| Any Indic | English | Whisper `translate` task (Kannada: Indic ASR → IndicTrans2) |
| Any | Any other (e.g. Hindi→Kannada, English→Hindi) | ASR → IndicTrans2 distilled 200M |

Handles Hinglish code-switching; supports native scripts (Devanagari, Kannada) with optional
romanized output. Language can be auto-detected or pinned per profile.

---

## Why local beats the paid apps (honest version)

**Wins:** privacy (no audio leaves the device) **and** free/OSS **together** — rivals give
one or the other; Indic-first multilingual + translation (under-served by cloud flow apps);
own-your-stack (swappable models, editable cleanup, local history, no telemetry); no network
latency. **Where cloud can still win:** biggest server+LLM stacks on worst-case accuracy,
zero-setup polish, cross-device sync — we don't over-claim on those. See [08](08-competitive-comparison.md).

---

## Cross-platform (NVIDIA is the baseline build)

NVIDIA → faster-whisper CUDA / Ollama CUDA. AMD → whisper.cpp **Vulkan** on Windows, ROCm on
Linux (CTranslate2 ROCm landed 2026-02, bleeding-edge). Apple Silicon → mlx-whisper /
whisper.cpp Metal (best per-watt). Intel → whisper.cpp OpenVINO. CPU → whisper.cpp tiny/distil.
Portability rests on a **minimal abstraction: two Protocols — `STTEngine` and `LLMEngine`** —
everything else (audio, hotkey, injection, history) is identical. **Biggest risk: AMD on
Windows.** See [07](07-cross-platform-scaling.md).

---

## Open items to verify before/at implementation

- PortAudio `WasapiSettings` flag names + whether session-category control is needed, or
  default non-comms shared capture suffices (validate on real hardware) — [04](04-audio-capture-no-artifacts.md).
- Current best small local LLM + exact Ollama model tags — [06](06-text-formatting-cleanup.md).
- Live model benchmark numbers and current Indic model releases (docs written with the web
  gateway down; several figures labeled *unverified (2026)*) — [02](02-stt-models-and-benchmarks.md), [03](03-multilingual-and-translation.md).
