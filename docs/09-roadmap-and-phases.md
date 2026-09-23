# 09 — Roadmap & Build Phases

Phased so each stage is a **usable app**, not scaffolding. Ship the lazy version first,
harden later. Locked stack and rationale in [00-overview-and-decisions.md](00-overview-and-decisions.md).

---

## Phase 0 — Skeleton & environment (½ day)

- Python project, venv, deps: `faster-whisper`, `sounddevice`, `soxr`/`scipy`, `keyboard`,
  clipboard lib, `silero-vad`, `ollama` client (later phases).
- Confirm CUDA + faster-whisper load large-v3-turbo on the target GPU.
- Config file (flat JSON): hotkey, device, model, language, output-language, cleanup mode,
  history size.

**Exit:** `python -m wisper` starts headless, loads the model, logs "ready".

## Phase 1 — MVP: the core loop (the whole product in one thread) ⭐

The end-to-end value. English only, default light cleanup, batch-on-stop.

1. **Global hotkey** (`keyboard`, toggle): press → start capture, press → stop. [05](05-text-injection-and-hotkeys.md)
2. **Audio capture** done right from day one: WASAPI **shared, non-comms**, native rate →
   16 kHz mono, ring buffer. This is non-negotiable — the no-ducking behavior is a core
   feature, not a later fix. [04](04-audio-capture-no-artifacts.md)
3. **Transcribe on stop**: faster-whisper large-v3-turbo, float16, on the buffered audio. [02](02-stt-models-and-benchmarks.md)
4. **Rule-based cleanup** (delete-only: fillers, stutters, repeats, false starts + punct/caps). [06](06-text-formatting-cleanup.md)
5. **Atomic paste**: save clipboard → set text → Ctrl+V → restore. Ctrl+Shift+V branch for
   terminals. [05](05-text-injection-and-hotkeys.md)

**Exit / acceptance:** hotkey → speak a paragraph → stop → cleaned text pastes at once into
Notepad, VS Code, a browser box, and the Claude Code terminal. **Ducking regression test
passes** (music volume unchanged while recording — [04](04-audio-capture-no-artifacts.md) test plan).

## Phase 2 — History & config polish (½–1 day)

- **SQLite** last-N history (ring-buffer prune), size configurable. [01](01-architecture-and-pipeline.md)
- Re-paste from history; copy from history.
- Device picker; hotkey rebind; mic-permission detection with a clear message.

**Exit:** last N transcripts persist across restarts and can be re-pasted.

## Phase 3 — Multilingual + translation (1–2 days)

- Language selection: auto-detect or pinned; separate **spoken** vs **output** language. [03](03-multilingual-and-translation.md)
- Hindi via large-v3; **Kannada via AI4Bharat Indic ASR**.
- **Speak X → paste English** via Whisper `translate` task.
- **Speak X → paste any language** via ASR → **IndicTrans2 distilled 200M**.
- Unicode paste verified for Devanagari/Kannada (already covered by clipboard-paste). [05](05-text-injection-and-hotkeys.md)

**Exit:** speak Hindi → paste English works; speak Kannada → paste Kannada works; Hinglish
doesn't break.

## Phase 4 — LLM cleanup + optimize button (1 day)

- **Ollama + Qwen2.5-3B (Q4)**; Gemma-2-2B fallback. [06](06-text-formatting-cleanup.md)
- **LIGHT** (LLM, guarded by token-subsequence/overlap check, temp 0.0 → falls back to
  rule-based on drift) and **POLISH** (opt-in) modes.
- **Optimize/refresh** action: rule → LLM-light → polish escalation, non-destructive undo.
- Latency strategy: paste instant rule-based result; LLM refines on demand.

**Exit:** default stays exact-wording; optimize button produces a cleaner version locally;
no hallucinated words in LIGHT mode.

## Phase 5 — Incremental transcription (optional, only if needed)

- Only if long-utterance stop→paste latency is actually felt.
- VAD-chunked background transcription during recording; cleanup still runs once on the full
  text; partials never shown until stop. [01](01-architecture-and-pipeline.md) (Design B)

## Phase 6 — UI (deferred; liquid-glass)

- Separate process over **loopback-socket JSON IPC**; core already headless. [01](01-architecture-and-pipeline.md)
- Tray + recording indicator + history + settings + optimize button.
- Visual design (liquid glass) specced separately once fundamentals are locked.

## Phase 7 — Cross-platform (as demand appears)

- Slot alternate backends behind the `STTEngine`/`LLMEngine` Protocols. [07](07-cross-platform-scaling.md)
- Order of effort: CPU fallback (whisper.cpp) → Apple Silicon (mlx-whisper) → AMD (Vulkan,
  the riskiest) → Intel (OpenVINO).
- Packaging per OS (PyInstaller one-file; installer documents CUDA prereqs).

---

## Dependency graph (what blocks what)

```
Phase 0 ─▶ Phase 1 (MVP) ─▶ Phase 2 (history)
                     └─────▶ Phase 3 (multilingual)
                     └─────▶ Phase 4 (LLM cleanup)
Phase 1 ───────────────────▶ Phase 5 (incremental, optional)
Phase 1 ───────────────────▶ Phase 6 (UI)
Phases 1–4 ────────────────▶ Phase 7 (cross-platform)
```

Phases 2, 3, 4 are **independent** of each other → good candidates to parallelize across
subagents once Phase 1 is solid. Phase 1 is strictly sequential and must be rock-solid first.

## Definition of done for v1.0

Windows + NVIDIA. Hotkey dictation into any app; sub-1.5 s perceived latency on short
phrases; **no audio ducking**; English + Hindi + Kannada with translate-to-English and
any-language output; default exact-wording cleanup + optimize button; configurable local
history; no data leaves the device.
