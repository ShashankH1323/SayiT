# Wisper — Research & Design Docs

**Wisper** is a fully local, free, open-source alternative to Wispr Flow: press a global
hotkey → speak → press again → the full, cleaned transcript pastes at once wherever your
cursor is. No cloud, no subscription, no telemetry. Windows 11 + NVIDIA CUDA first;
multilingual (English + Hindi + Kannada + Indic) with a choosable output language.

**Start here:** [00 — Overview & Locked Decisions](00-overview-and-decisions.md) (the stack
and the *why*) and [09 — Roadmap & Phases](09-roadmap-and-phases.md) (the build plan).

## Index

| # | Doc | What it covers |
|---|-----|----------------|
| 00 | [Overview & Decisions](00-overview-and-decisions.md) | The locked stack, the one key insight, cleanup modes, multilingual routing, open items |
| 01 | [Architecture & Pipeline](01-architecture-and-pipeline.md) | End-to-end flow, threading model, atomic paste, batch-vs-incremental, storage, UI IPC boundary |
| 02 | [STT Models & Benchmarks](02-stt-models-and-benchmarks.md) | Engine/model choice for CUDA — faster-whisper + large-v3-turbo, fallbacks, quantization, VAD |
| 03 | [Multilingual & Translation](03-multilingual-and-translation.md) | Hindi/Kannada/Indic + English; speak-X-paste-Y; Whisper translate, AI4Bharat, IndicTrans2 |
| 04 | [Audio Capture Without Artifacts](04-audio-capture-no-artifacts.md) | **The no-ducking fix** — WASAPI shared, non-comms role, clean resample, VAD, test plan |
| 05 | [Text Injection & Hotkeys](05-text-injection-and-hotkeys.md) | Toggle hotkey + instant clipboard-paste anywhere, Unicode/Indic, terminal edge cases |
| 06 | [Text Formatting & Cleanup](06-text-formatting-cleanup.md) | Default exact-wording light cleanup vs opt-in polish, Ollama model, the optimize button |
| 07 | [Cross-Platform Scaling](07-cross-platform-scaling.md) | NVIDIA baseline + AMD/Mac/Intel/CPU via a minimal engine abstraction |
| 08 | [Competitive Comparison](08-competitive-comparison.md) | Honest comparison vs Wispr Flow / Superwhisper / etc. and where local wins |
| 09 | [Roadmap & Phases](09-roadmap-and-phases.md) | Phased build plan, dependency graph, v1.0 definition of done |

## Notes

- The web gateway was intermittently down during authoring; figures that couldn't be
  verified online are labeled **"unverified (2026)"** and flagged for confirmation at
  implementation time (mainly in docs 02, 03).
- Next step after review: begin **Phase 1 (MVP)** from [09](09-roadmap-and-phases.md).
