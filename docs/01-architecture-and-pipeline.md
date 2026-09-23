# Wisper — 01: System Architecture & Data Flow

Status: design draft · Date: 2026-09-22 · Scope: end-to-end architecture only.
Deep-dives live in sibling docs: STT models/benchmarks (`02`), Indic + translation
(`03`), audio artifacts / no-ducking capture (`04`), hotkey + text injection (`05`),
cleanup prompts (`06`). This doc references them by name and does not repeat them.

---

## 1. What Wisper is (one paragraph)

A single always-on **local background service**. A global hotkey toggles recording
on; the user speaks; the hotkey again stops it; the service transcribes the whole
utterance locally, cleans it (remove disfluencies, optionally translate/rewrite),
and injects the **entire cleaned paragraph at once** at the current text cursor via
clipboard + Ctrl+V. No cloud, no audio ducking. A future UI attaches to the core
over a local IPC boundary without touching core logic.

---

## 2. Component / module breakdown

| Module | Responsibility | Primary lib (hypothesis) | Doc |
|---|---|---|---|
| `hotkey` | Global toggle listener, debounced | `pynput` (fallback `keyboard`) | 05 |
| `audio` | WASAPI **shared-mode** capture, ring buffer, no ducking | `sounddevice`/PortAudio | 04 |
| `vad` | Voice-activity segmentation (Design B; silence-trim in A) | Silero VAD | 02/04 |
| `stt` | Speech→text, batch or incremental | faster-whisper (CTranslate2, CUDA) | 02 |
| `clean` | Disfluency removal / translation / opt-in rewrite | Ollama + small LLM | 03/06 |
| `inject` | Clipboard set + Ctrl+V paste, clipboard restore | `pyperclip` + `pynput` | 05 |
| `state` | Central state machine + event bus | stdlib (`enum`, `queue`) | — |
| `store` | Config + last-N transcript history | SQLite (see §9) | — |
| `ipc` | Boundary for future UI | local socket / stdin-stdout (§10) | — |

All modules are plain Python objects behind small interfaces (§11). Everything but
`stt` and `clean` is thin glue — those two are the only swappable "backends".

### ASCII architecture

```
                        ┌─────────────────────────────────────────────┐
                        │            Wisper Core (one process)          │
                        │                                               │
  [Global Hotkey] ─────►│  hotkey ──► StateMachine ◄── event bus (queue)│
                        │                 │                             │
   OS mic (WASAPI       │                 ▼                             │
   shared, no duck) ───►│  audio.callback ──► ring buffer ──► [VAD]     │
                        │        (RT thread)          │                 │
                        │                             ▼                 │
                        │                     stt worker (CUDA)         │
                        │                             │                 │
                        │                             ▼                 │
                        │                     clean worker (Ollama)     │
                        │                             │                 │
                        │                             ▼                 │
                        │                  inject (clipboard + Ctrl+V) ─┼──► active
                        │                             │                 │    window
                        │                             ▼                 │
                        │                    store (SQLite history)     │
                        │                                               │
                        │  ipc endpoint  ◄────────────────────────────  │
                        └──────────────────┬────────────────────────────┘
                                           │ (local socket / stdio)
                                    ┌──────▼───────┐
                                    │  Future UI    │  (separate process,
                                    │  (deferred)   │   optional, later)
                                    └───────────────┘
```

---

## 3. Data flow (record → transcribe → clean → inject)

```
hotkey ON
  → audio callback streams frames → ring buffer (+ VAD in Design B)
hotkey OFF
  → finalize buffer → hand PCM to stt worker
  → transcript text → clean worker (mode: disfluency | translate | rewrite)
  → cleaned text → set clipboard → send Ctrl+V → restore clipboard
  → persist {raw, cleaned, lang, ts} to history → back to idle
```

The audio callback thread never blocks on STT/LLM. Heavy work happens on worker
threads fed by queues, so capture stays glitch-free (detail in doc 04).

---

## 4. State machine

```
        hotkey                stop               done            done
 IDLE ─────────► RECORDING ─────────► TRANSCRIBING ───► CLEANING ───► PASTING ──┐
   ▲                 │  (Design B: chunks transcribe in background here)         │
   │                 │ hotkey/cancel                                             │
   └─────────────────┴──────────────◄── ERROR ◄── (any worker failure) ─────────┘
                                    (toast + return to IDLE, no paste)
```

| State | Enters on | Exits on | Notes |
|---|---|---|---|
| IDLE | boot / paste done / cancel | hotkey | Only hotkey listener active |
| RECORDING | hotkey | hotkey (stop) / cancel | Audio flowing; B transcribes chunks live |
| TRANSCRIBING | stop | STT returns | A: whole clip; B: only tail |
| CLEANING | STT done | LLM returns / skipped | Skippable if cleanup disabled |
| PASTING | clean done | inject returns | Clipboard swap + Ctrl+V |
| ERROR | any failure | auto → IDLE | Never partial-pastes |

"Refresh/optimize" re-runs CLEANING on the stored `raw` transcript of the last
entry and re-pastes — a state re-entry, not a new recording.

---

## 5. Concurrency / threading model

Single process, threads (not multiprocessing) for core — CUDA context and model
stay warm in one address space; the GIL is released during CTranslate2/torch native
calls and during I/O, so threads are enough. Queues decouple stages.

| Thread | Type | Blocking? | Talks to |
|---|---|---|---|
| Audio callback | PortAudio RT | Must never block | writes ring buffer only |
| Hotkey listener | pynput daemon | no | posts events to bus |
| STT worker | worker | yes (GPU) | audio queue → text queue |
| Clean worker | worker | yes (Ollama HTTP) | text queue → paste queue |
| Inject | runs on state thread | brief (~ms) | OS clipboard/keys |
| IPC server | daemon (later) | no | reads state, posts commands |
| Future UI | **separate process** | — | over IPC only |

Model is loaded once at boot and reused (avoid per-utterance load cost). One
in-flight utterance at a time (a mutex/`is_busy` guard); a new hotkey while busy is
queued or ignored (config). `ponytail:` single global lock is fine here — throughput
is one human talking; per-utterance parallelism is YAGNI.

---

## 6. How the whole paragraph appears at once

The paste is **one atomic clipboard write + one Ctrl+V**, never per-word keystroke
injection. This is the deliberate difference from WhisperWriter, which types
keystrokes one at a time. Rationale:

- The full cleaned text exists before any paste happens (clean stage completes first).
- Clipboard paste is a single OS event → target app receives the whole block at once,
  works in any input (VS Code, terminal, browser), and is far faster than simulated
  typing for long text.
- Prior clipboard contents are saved and restored after paste (detail in doc 05).

Both designs below still show the user **one** final result and paste **once**;
Design B just makes that final moment near-instant.

---

## 7. Two designs

### Design A — MVP: batch-on-stop (ship this first)

```
RECORDING: accumulate all PCM in ring buffer (optionally VAD-trim leading/trailing silence)
STOP:      transcribe entire clip in one faster-whisper call → clean → paste
```

- Simplest correct thing. One STT call, deterministic, easiest to get accurate
  across languages. Latency scales with utterance length (see §8).
- Matches the proven WhisperWriter model minus the cloud fallback and keystroke typing.

### Design B — Optimized: background-incremental (VAD-chunked)

```
RECORDING: VAD splits speech into segments; each finalized segment is transcribed
           on the STT worker WHILE the user keeps talking. Confirmed text buffers.
STOP:      only the short trailing segment remains → transcribe tail (fast)
           → concat confirmed + tail → clean once → paste once
```

- On stop, nearly all audio is already transcribed, so perceived latency ≈ tail
  transcribe + clean, roughly constant regardless of utterance length.
- Borrows the **LocalAgreement-2** idea from `whisper_streaming` (commit a prefix
  once two successive passes agree) to keep confirmed text stable, but Wisper only
  *displays/pastes on stop* — partials are internal, never pasted, so we sidestep the
  hardest part of live streaming (flickering output).
- Cleanup and translation still run **once on the full concatenated transcript** at
  stop, so quality matches Design A. Do not clean per-chunk (context loss, cost).
- Cost: VAD tuning, segment boundary handling, prompt-carry across chunks. Defer to
  after A works. Upstream now favors SimulStreaming over whisper_streaming for
  speed — evaluate in doc 02 before committing.

`ponytail:` B is a real optimization with a real ceiling (VAD/boundary complexity).
Ship A; add B only if measured stop→paste latency on long utterances annoys the user.

---

## 8. Latency budget (rough, mid/high NVIDIA GPU, ~15 s utterance)

faster-whisper large-v3 int8_float16 runs ~5–15× realtime on RTX 3060–4090.
Numbers below are order-of-magnitude planning targets, not benchmarks (see doc 02).

| Stage | Design A | Design B | Notes |
|---|---:|---:|---|
| stop → buffer finalize | ~10–30 ms | ~10–30 ms | copy ring buffer |
| transcribe | ~1000–2500 ms (whole 15 s) | ~200–600 ms (tail only) | GPU dependent |
| clean (small LLM, ~100 tok) | ~300–1500 ms | ~300–1500 ms | model kept warm |
| set clipboard + Ctrl+V | ~20–80 ms | ~20–80 ms | + clipboard restore |
| **perceived stop → paste** | **~1.5–4 s** | **~0.8–2 s** | B ~constant vs length |

Biggest lever after STT is keeping the Ollama model warm (first call cold-loads).
Cleanup can be skipped entirely (disfluency-off mode) to cut the LLM stage.

---

## 9. Config & history storage

| Need | Choice | Why |
|---|---|---|
| Config (hotkey, model, device, langs, mode) | **flat JSON** (`config.json`) | Human-editable, tiny, no schema churn, load once at boot |
| History (last-N transcripts) | **SQLite** (`history.db`) | Bounded ring of rows, indexed by timestamp, cheap `DELETE`/`LIMIT`, concurrent read from future UI, survives crash mid-write; stdlib `sqlite3`, zero deps |

Rationale for the split: config is read rarely and edited by humans → JSON wins on
simplicity. History is appended per utterance, queried by the UI, and pruned to
last-N → a real (if tiny) query workload where SQLite's indexing, atomic writes, and
concurrent reads beat rewriting a growing JSON file every utterance. `ponytail:`
one table `transcripts(id, ts, raw, cleaned, lang_in, lang_out, mode)`; prune with
`DELETE ... WHERE id NOT IN (SELECT id ... ORDER BY ts DESC LIMIT N)`. No ORM.

Privacy flag: transcripts are speech content — store in the user profile dir, offer a
"clear history" and a "history off" switch. Never sync off-device.

---

## 10. Core ↔ future-UI boundary

The core runs headless and owns all logic. The UI (deferred) is a **separate
process** that only observes state and sends commands over a local IPC channel.

| Option | Verdict |
|---|---|
| **Local loopback socket (127.0.0.1) w/ line-delimited JSON** | **Recommended.** Bidirectional, lets UI subscribe to state-change events + send commands (start/stop, re-clean, get history); trivial in stdlib (`socketserver`/`asyncio`); language-agnostic if UI is ever non-Python |
| stdin/stdout pipe | OK only if UI always launches core as child; brittle for an always-on service |
| Local HTTP + WebSocket | Heavier; adds a web dep; reserve if UI becomes a browser app |

Contract: a small JSON message protocol — events (`state_changed`, `transcript_ready`)
and commands (`toggle`, `recleanse`, `list_history`, `get_config`, `set_config`).
Core has zero UI imports; it works fully with no UI attached.

---

## 11. Extensibility (swappable backends)

Two seams only — keep everything else concrete (YAGNI on abstraction).

```
class SttBackend(Protocol):
    def transcribe(self, pcm, lang_in, lang_out) -> str: ...

class CleanBackend(Protocol):
    def clean(self, text, mode, lang_out) -> str: ...   # mode: none|disfluency|translate|rewrite
```

- STT default: `FasterWhisperBackend`. Alternates (whisper.cpp, SimulStreaming,
  cloud) drop in behind the same Protocol — chosen in `config.json`.
- Clean default: `OllamaBackend`. Alternate: `NoopBackend` (disfluency-off / passthrough)
  or a rules-only filler stripper for zero-latency mode.
- No plugin framework, no registry, no factory — just a name→class map read from config.
  Add abstraction only when a third real backend exists.

---

## Assumptions & open questions for synthesis

- **Threads vs process for STT:** assumed threads suffice (native calls release GIL).
  If Python-side pre/post-processing becomes a bottleneck, revisit a subprocess STT
  worker. (Confirm in doc 02.)
- **Design B necessity:** assumed A is enough for MVP; B only if long-utterance
  stop→paste latency is felt. Needs real latency measurement to decide.
- **whisper_streaming vs SimulStreaming:** upstream calls whisper_streaming outdated.
  Doc 02 should pick the incremental engine for Design B.
- **One-utterance-at-a-time lock:** assumed acceptable (single human speaker). Flag if
  multi-recording queueing is ever wanted.
- **Cleanup always at stop, never per-chunk:** assumed for quality; confirm with doc 06
  that full-context cleanup is required (it is, for disfluency + translation coherence).
- **IPC auth:** loopback socket is unauthenticated by default — fine for single-user
  localhost, but note it so a future multi-user or container scenario adds a token.
- **Clipboard as the injection channel** carries a small privacy footprint (transcript
  briefly on the system clipboard); doc 05 owns the restore/secure-clear behavior.

## Sources

- WhisperWriter (local hotkey dictation, faster-whisper, recording modes, injection): https://github.com/savbell/whisper-writer
- whisper_streaming — LocalAgreement-2, VAD/VAC, buffer trimming, ~3.3 s latency, points to SimulStreaming: https://github.com/ufal/whisper_streaming
- faster-whisper (CTranslate2 CUDA STT engine): https://github.com/SYSTRAN/faster-whisper
- Silero VAD (voice-activity segmentation): https://github.com/snakers4/silero-vad
- Ollama (local LLM runtime for cleanup): https://github.com/ollama/ollama
