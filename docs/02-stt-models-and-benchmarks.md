# 02 — STT Models & Benchmarks

> Scope: pick the speech-to-text **engine + model + precision** for Wisper — a fully local, free Wispr Flow clone. Hotkey starts/stops recording; the whole utterance is transcribed after stop, cleaned, and pasted at once. Target: Windows 11 + NVIDIA CUDA GPU. No cloud.
>
> **All WER / speed / VRAM figures below are estimates** drawn from public leaderboards and community benchmarks up to early 2026. Anything I could not verify against a source in this session is tagged **`unverified (2026)`**. Numbers vary heavily with audio domain, batch size, VAD settings, and driver/CUDA versions — treat them as ranking guides, not contracts.

---

## Recommendation (read this first)

| Role | Model | Engine | Precision | Why |
|------|-------|--------|-----------|-----|
| **Primary default** | **Whisper large-v3-turbo** | **faster-whisper (CTranslate2)** | **float16** (or `int8_float16` on ≤8 GB) | Best accuracy/speed balance, multilingual, punctuation+casing built in, trivial Windows/CUDA install, batching + word timestamps. Confirms the working hypothesis. |
| **Lighter fallback** (weak GPU / 4–6 GB / CPU) | **distil-large-v3** or **Whisper medium** | faster-whisper | `int8_float16` (GPU) / `int8` (CPU) | ~2× faster than large-v3-turbo, ~2 GB VRAM, still good English. distil is English-first; use `medium` if multilingual needed. |
| **Max accuracy** | **Whisper large-v3** | faster-whisper (or WhisperX for alignment) | float16 | Lowest Whisper-family WER, best multilingual/Indic. ~2–3× slower than turbo but for short dictation utterances the wall-clock cost is small. |
| **Watch / optional** | **NVIDIA Parakeet TDT 0.6B v2** | NeMo | bf16/fp16 | English-only but tops the Open ASR leaderboard on WER **and** speed; worth a spike if English-only is acceptable. Heavier install. |

**Deviation from hypothesis:** none of substance. Hypothesis (faster-whisper on CUDA, large-v3 / large-v3-turbo) holds. The one refinement: default to **turbo**, not full large-v3 — turbo is dramatically faster with a tiny English WER penalty, which matters for the "paragraph appears instantly after stop" feel. Keep large-v3 as the max-accuracy toggle.

---

## Requirements

What the STT layer actually has to do for Wisper:

- **Batch (not streaming) transcription.** The whole clip is available the moment the user hits stop. We do **not** need live partial hypotheses. This widens our options — streaming-only engines get no bonus, and offline decoding is more accurate than streaming.
- **Fast turnaround after stop.** Perceived latency = (audio length) × (1 / real-time factor) + model overhead. For a ~10 s utterance at RTF 10× that's ~1 s. Anything under ~1–1.5 s feels instant. This is the real KPI, not throughput on hour-long files.
- **Punctuation + capitalization out of the box.** Whisper and Canary produce cased, punctuated text. Raw CTC models (Parakeet CTC, older NeMo) often do not — that pushes cleanup work into doc 01/cleanup stage.
- **Multilingual** desired (Indic quality is doc 03's call) — flagged per model below.
- **Simple Windows + CUDA install.** Weighs heavily. faster-whisper is a `pip install`; NeMo drags in a large dependency tree.
- **Free / open weights**, local only.
- **Modest VRAM** so it coexists with the OS and a browser on a 6–8 GB laptop GPU.

---

## Candidate engines

| Engine | Backend | Windows+CUDA install | Strengths | Weaknesses |
|--------|---------|----------------------|-----------|------------|
| **faster-whisper** | CTranslate2 | `pip install faster-whisper` (+cuDNN). Easiest. | 4–5× faster than PyTorch Whisper, low VRAM, int8/int8_float16 quant, built-in Silero VAD, batched inference, word timestamps. | Whisper-family models only. |
| **whisper.cpp** | GGML/GGUF, C++ | Prebuilt CUDA/Vulkan binaries; no Python needed. | Tiny footprint, runs anywhere (CPU/CUDA/Metal/Vulkan), great for CPU fallback and shipping a single binary. | Slower than CTranslate2 on CUDA; fewer knobs; Python binding is secondary. |
| **openai-whisper** | PyTorch | `pip install openai-whisper` | Reference implementation, always first to get new checkpoints. | Slowest, highest VRAM, no built-in VAD. Reference only. |
| **WhisperX** | faster-whisper + wav2vec align + pyannote diarize | pip, heavier deps | Accurate word timestamps, VAD batching, speaker diarization. | Overkill for dictation (we don't need diarization/precise alignment); extra deps + HF token for diarization. |
| **distil-whisper** | HF Transformers / faster-whisper / whisper.cpp | pip | Distilled Whisper, ~2× faster, ~half the params, near-large English WER. | English-centric (distil-large-v3 primarily English); it's a *model*, run it under faster-whisper. |
| **NVIDIA NeMo** | PyTorch | Non-trivial on Windows (WSL2 recommended); large deps. | Hosts Parakeet & Canary — current WER/speed leaders. | Heavy install, Windows-native support fiddly, bigger operational surface. |

**Engine verdict:** faster-whisper for the default. whisper.cpp as the portable/CPU fallback. NeMo only if we commit to Parakeet/Canary.

---

## Candidate models

| Model | Params | Multilingual | Punct/Case | Notes |
|-------|--------|--------------|------------|-------|
| **Whisper large-v3** | 1.55B | ✅ 99 langs (strong Indic) | ✅ | Best Whisper WER; the accuracy ceiling for this family. |
| **Whisper large-v3-turbo** | ~0.8B (4 decoder layers) | ✅ (slightly weaker on some langs) | ✅ | Pruned decoder → much faster, tiny English WER hit. **Default pick.** |
| **Whisper medium** | 769M | ✅ | ✅ | Solid multilingual mid-tier; good CPU/weak-GPU option. |
| **distil-large-v3** | ~756M | ⚠️ English-first | ✅ | ~2× faster than large-v3, near-large English WER. Weak/none on many languages. |
| **NVIDIA Parakeet TDT 0.6B v2** | 0.6B | ❌ English only | ✅ (v2 adds punct/case) | Tops Open ASR leaderboard on WER + throughput. English dictation champion. |
| **NVIDIA Parakeet TDT/CTC 1.1B** | 1.1B | ⚠️ some multilingual variants | mixed | Larger; CTC variant may lack punctuation. |
| **NVIDIA Canary 1B** | 1B | ✅ (EN/DE/ES/FR + more in Canary-1B-Flash) | ✅ | Strong multilingual WER, also does translation. Heavier, NeMo-only. |
| **Canary-1B-Flash / Canary-180M-Flash** | 1B / 180M | ✅ | ✅ | Faster Canary variants; Flash-180M is a fast small multilingual option. |

**Other 2026-era open ASR to keep on the radar** — `unverified (2026)`: IBM/NVIDIA **Granite-speech**, **Moonshine** (tiny, low-latency, edge-focused, English), **Whisper large-v3** community fine-tunes for Indic, and ongoing Parakeet multilingual releases. None displaces the recommendation for a simple local Windows MVP.

---

## Benchmark table (estimates)

English WER on clean-ish speech; **RTF = audio seconds transcribed per wall-clock second (higher = faster)**; VRAM at float16 unless noted. GPU rows are order-of-magnitude community estimates, **all `unverified (2026)`** and scaled by relative GPU throughput (3060 ≈ baseline, 4070 ≈ ~1.7×, 4090 ≈ ~3–4×).

| Model (engine, precision) | ~EN WER | VRAM | RTF 3060 | RTF 4070 | RTF 4090 | ~10 s utterance latency | Streaming |
|---|---|---|---|---|---|---|---|
| large-v3 (faster-whisper, fp16) | ~2.5–4% | ~4.5–5 GB | ~8–12× | ~15–20× | ~30–50× | ~0.8–1.3 s | via chunking |
| large-v3 (fw, int8_float16) | ~2.5–4% | ~3 GB | ~10–15× | ~18–25× | ~40–60× | ~0.7–1.1 s | via chunking |
| **large-v3-turbo (fw, fp16)** | **~3–5%** | **~3–4 GB** | **~15–25×** | **~30–45×** | **~60–100×** | **~0.4–0.8 s** | via chunking |
| large-v3-turbo (fw, int8_float16) | ~3–5% | ~2–2.5 GB | ~20–30× | ~40–55× | ~80–120× | ~0.3–0.7 s | via chunking |
| medium (fw, int8_float16) | ~4–6% | ~1.5–2 GB | ~25–40× | ~45–65× | ~90–140× | ~0.3–0.6 s | via chunking |
| distil-large-v3 (fw, int8_float16) | ~3.5–5.5% (EN) | ~1.5–2 GB | ~30–50× | ~55–80× | ~110–160× | ~0.25–0.5 s | via chunking |
| large-v3-turbo (whisper.cpp, Q5) | ~3–5% | ~2 GB | ~8–15× | ~15–25× | ~30–50× | ~0.7–1.2 s | via chunking |
| large-v3 (openai-whisper, fp16) | ~2.5–4% | ~10 GB | ~2–4× | ~4–7× | ~10–15× | ~2.5–5 s | no |
| Parakeet TDT 0.6B v2 (NeMo, bf16) | **~1.5–2.5%** (EN, leaderboard-best) | ~2.5–3 GB | ~30–60× | ~60–100× | ~150–250×+ | ~0.2–0.4 s | ✅ (variants) |
| Canary-1B (NeMo, bf16) | ~2.5–4% (multiling) | ~5–6 GB | ~8–15× | ~15–25× | ~35–60× | ~0.8–1.3 s | limited |

**CPU note:** whisper.cpp or faster-whisper `int8` on a modern multi-core CPU runs `medium`/`turbo` around **RTF 0.5–2×** — usable as a last-resort fallback (a 10 s clip = ~5–20 s wait), acceptable when no GPU exists.

Takeaway: for short dictation clips, **every GPU option finishes in well under ~1.5 s** — so accuracy and install simplicity, not raw speed, should drive the default. Turbo is the sweet spot.

---

## Quantization tradeoffs (CTranslate2 / faster-whisper)

| Precision | VRAM vs fp16 | Speed | Quality impact | When to use |
|-----------|-------------|-------|----------------|-------------|
| **float16** | baseline | fast | reference (no loss) | Default on ≥8 GB GPUs. |
| **int8_float16** | ~40–50% less | fast–faster | negligible WER change (typically <0.3 pts) `unverified` | **Best default for constrained GPUs (≤8 GB).** int8 weights, fp16 compute. |
| **int8** | lowest | fast on CPU, ~same on GPU | small WER bump, occasional artifacts | CPU inference, or very tight VRAM. |
| **float32** | 2× fp16 | slowest | reference | Almost never needed; debugging only. |

Rule of thumb: **fp16 if VRAM allows, else int8_float16.** The quality difference is usually inaudible for dictation, and int8_float16 halves VRAM so the model comfortably shares an 8 GB laptop GPU with the OS.

---

## VAD / endpointing

- **Silero VAD** is built into faster-whisper (`vad_filter=True`). It strips leading/trailing/inter-word silence before decoding. Benefits for Wisper:
  - **Fewer hallucinations** — Whisper invents text on pure silence; VAD removes those regions.
  - **Faster** — less audio to decode when the user pauses or leaves dead air after pressing the hotkey.
  - **Cleaner output** — no phantom "Thank you." / "Thanks for watching." on silent tails (a well-known Whisper artifact).
- **Endpointing:** because Wisper uses an explicit **hotkey to stop**, we do **not** need automatic VAD-based endpointing to decide when speech ends — the user tells us. VAD is used purely as a *pre-filter on the captured clip*, not as a live turn-detector. Keep it simple.
- Tunables worth exposing: `min_silence_duration_ms` (default ~500 ms) and a small speech pad so word onsets aren't clipped. Start with defaults.
- **Recommendation:** enable Silero VAD filtering by default. It's free, bundled, and directly kills the two worst Whisper failure modes (silence hallucination + wasted decode time).

---

## Licensing & download sizes

| Model | License | Commercial use | Approx download |
|-------|---------|----------------|-----------------|
| Whisper large-v3 / turbo / medium | **MIT** (OpenAI) | ✅ yes | large-v3 ~3.1 GB fp16 · turbo ~1.6 GB · medium ~1.5 GB (CT2 int8 roughly half) |
| distil-large-v3 | **MIT** | ✅ yes | ~1.5 GB |
| whisper.cpp GGUF (turbo, Q5) | MIT (model) | ✅ | ~0.8–1.6 GB depending on quant |
| NVIDIA Parakeet TDT 0.6B v2 | **CC-BY-4.0** | ✅ (attribution) | ~2.4 GB `unverified` |
| NVIDIA Canary 1B / Flash | **CC-BY-4.0** (check per-checkpoint) `unverified` | ✅ (attribution) | ~1.8–4 GB `unverified` |

All candidates are **free and open-weight** and satisfy the "local + free" requirement. Whisper's MIT license is the most permissive; NVIDIA's CC-BY-4.0 just requires attribution.

CTranslate2 auto-downloads Whisper checkpoints from HF on first use and caches them — no manual model management needed for the MVP.

---

## Assumptions & open questions (for synthesis)

**Assumptions:**
1. Batch-after-stop, not live streaming — so offline decoding accuracy applies and streaming support is a non-factor.
2. Perceived latency on **short (~5–20 s) utterances** is the KPI, not long-form throughput. All GPU options pass easily.
3. Target GPU has ≥4 GB VRAM; ≥8 GB is comfortable. A CPU fallback exists but is slow.
4. Punctuation/casing from the model is preferred over reconstructing it in cleanup.

**Open questions:**
1. **English-only acceptable?** If yes, Parakeet TDT 0.6B v2 beats Whisper on both WER and speed — but adds a heavy NeMo/Windows install. Is the WER win worth the install complexity for an MVP? (Leaning no for MVP, yes for a later "English turbo" mode.)
2. **Indic/multilingual quality** — deferred to doc 03. That doc should confirm whether large-v3 (full, not turbo) is needed for Indic, which would change the default per-language.
3. **cuDNN / CUDA packaging on Windows** — faster-whisper needs matching cuDNN DLLs; confirm the exact ctranslate2/cuDNN/driver combo during setup (doc 04/install).
4. **Model auto-download vs bundled** — first-run download is ~1.6–3 GB; decide whether to pre-bundle for offline install.
5. Verify the estimated benchmark numbers on our actual target GPUs before locking defaults — the table here is directional only.

---

## Sources

Live web search was unavailable during authoring; the following are the primary references this document is built from (consult directly to verify the estimated figures):

- OpenAI Whisper — https://github.com/openai/whisper
- faster-whisper (CTranslate2) — https://github.com/SYSTRAN/faster-whisper
- whisper.cpp — https://github.com/ggerganov/whisper.cpp
- WhisperX — https://github.com/m-bain/whisperX
- distil-whisper — https://github.com/huggingface/distil-whisper
- NVIDIA NeMo — https://github.com/NVIDIA/NeMo
- Hugging Face **Open ASR Leaderboard** (WER + RTF rankings for Whisper, Parakeet, Canary) — https://huggingface.co/spaces/hf-audio/open_asr_leaderboard
- Silero VAD — https://github.com/snakers4/silero-vad
- NVIDIA Parakeet TDT 0.6B v2 — https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2
- NVIDIA Canary — https://huggingface.co/nvidia/canary-1b

> Reminder: every quantitative figure above is an **estimate**; items tagged `unverified (2026)` were not confirmed against a live source in this session.
