# 03 — Multilingual Support & Translation

Scope: how Wisper handles English + Hindi + Kannada + other Indic languages, and how it lets the user pick an **output language independent of the spoken language** — all fully local, free/open models, on Windows 11 + NVIDIA CUDA.

> WER/quality numbers below are directional. Where marked **unverified (2026)** they are from memory, not re-confirmed against a live benchmark. Treat them as "which bucket" (good / decent / weak), not exact scores.

---

## TL;DR recommendations

- **English → English:** Whisper `large-v3` (or `distil-large-v3` if you want speed). Done.
- **Hindi → Hindi:** Whisper `large-v3` is *decent*; AI4Bharat **IndicWhisper** is meaningfully better if you want to invest.
- **Kannada → Kannada:** vanilla Whisper is *weak* here — use an **AI4Bharat Indic model** (IndicWhisper or IndicConformer).
- **Any Indic → English:** either Whisper's built-in **translate task** (simplest, one model, English-only) or **ASR → IndicTrans2** (better quality, needed for weak-ASR langs like Kannada).
- **Arbitrary pairs** (Hindi→Kannada, English→Hindi, etc.): **ASR → AI4Bharat IndicTrans2** as the local MT engine. Prefer it over NLLB-200 on both quality-for-Indic and licensing (IndicTrans2 is permissive; NLLB is non-commercial).

---

## 1. Language requirements

Three things must be independent:

1. **Spoken (source) language** — what the user actually says into the mic.
2. **Output (target) language** — what gets pasted.
3. **Output script** — Devanagari, Kannada script, or optional romanization.

Concrete cases the design must serve:

| # | Speak | Paste | Notes |
|---|-------|-------|-------|
| a | English | English | baseline |
| b | Hindi | Hindi | same-language transcription |
| c | Hindi | English | translation (English target) |
| d | Kannada | Kannada | weak-ASR language, same-language |
| e | Kannada | English | translation, weak source ASR |
| f | Hindi | Kannada | Indic↔Indic, no English endpoint |
| g | English | Hindi | reverse direction |
| h | Hinglish (mixed) | Hindi *or* English *or* keep-mixed | code-switching |

The key architectural point: **source ≠ target**, so ASR and MT are separate stages that are wired together by a routing decision (Section 6).

---

## 2. Whisper multilingual quality (realistic)

OpenAI Whisper (`large-v3` is the current best open checkpoint) covers ~99 languages. Quality is **very uneven** across Indic languages — driven by how much of each language was in training data.

| Language | Vanilla Whisper `large-v3` quality | Rough WER band |
|----------|-----------------------------------|----------------|
| English | excellent | ~5–10% |
| Hindi | **decent** — usable, occasional errors | ~20–35% WER on FLEURS-style eval *(unverified, 2026)* |
| Kannada | **weak** — frequent errors, sometimes unusable | ~40–80%+ WER; historically among Whisper's poorer Indic langs *(unverified, 2026)* |
| Other Indic (Tamil, Telugu, Marathi, Bengali, etc.) | mixed; Hindi-tier at best, Kannada-tier or worse for lower-resource ones | varies widely |

Practical takeaways:
- Hindi on plain Whisper `large-v3` is good enough to ship as a default.
- Kannada (and most South-Indian / lower-resource Indic langs) on plain Whisper is not — route these through an Indic-specialized model.
- Whisper auto-detects language from the first ~30s of audio. Detection is reliable for high-resource langs, shakier for low-resource ones and for short clips — a reason to prefer manual/remembered language (Section 9).

### Whisper's built-in translate task — important limitation

Whisper has two tasks: `transcribe` (source→source text) and `translate`. **The `translate` task ONLY outputs English.** It cannot produce Hindi, Kannada, or any non-English target. So it solves cases (c) and (e) — "any language → English" — in a single model pass, and nothing else. For any non-English target you need a separate MT stage.

---

## 3. Indic-specialized open models

These exist specifically because vanilla Whisper is weak on many Indic languages. All free/open, run locally on CUDA.

### ASR

- **AI4Bharat IndicWhisper** — Whisper (medium) fine-tuned on large Indic corpora (IndicSUPERB / Vistaar). Covers ~12 major Indian languages. Substantially lower WER than vanilla Whisper on Indic langs, especially the weaker ones like Kannada. Whisper-compatible, so it slots into the same inference stack. *Quality gains are large but exact numbers unverified (2026).*
- **AI4Bharat IndicConformer / IndicASR** — Conformer (CTC/RNNT) models built on NVIDIA **NeMo**. A single **multilingual** model covering ~22 scheduled Indian languages exists (e.g. the ~600M "indic-conformer" multilingual checkpoint). Strong on South-Indian languages where Whisper struggles. NeMo runtime is a separate dependency from Whisper — heavier to integrate but best-in-class for Kannada/Telugu/Tamil-tier langs.
- **NVIDIA NeMo Indic models** — AI4Bharat and NVIDIA have collaborated; the IndicConformer line is the practical output. If you already pull in NeMo for Conformer, you get these together.

**Recommendation:** start with **IndicWhisper** (same stack as Whisper, easy). Add **IndicConformer** only if Kannada/other South-Indian quality still isn't good enough — it's the stronger model but the heavier integration.

### MT (machine translation)

- **AI4Bharat IndicTrans2** — the recommended local MT engine. Translates **Indic↔English↔Indic** across ~22 languages, *including Indic-to-Indic directly* (Hindi→Kannada without bouncing through English). Sizes: ~1B params, plus a **distilled ~200M** variant for speed/VRAM. **Permissive license (MIT-style)** — usable commercially. This is the single most important model for the source≠target requirement.
- **Meta NLLB-200** — 200-language MT, sizes from distilled-600M up to 3.3B (and larger MoE). Broad coverage beyond Indic. **License: CC-BY-NC (non-commercial).** Quality on Indic pairs is generally *behind* IndicTrans2. Use only as a fallback for language pairs IndicTrans2 doesn't cover, and mind the non-commercial license.

| MT model | Coverage | Indic↔Indic direct? | Quality (Indic) | Speed / VRAM | License |
|----------|----------|---------------------|-----------------|--------------|---------|
| **IndicTrans2 (distilled 200M)** | 22 Indian langs + En | Yes | good | fast, low VRAM | permissive (MIT) ✅ |
| **IndicTrans2 (1B)** | same | Yes | better | slower, more VRAM | permissive ✅ |
| NLLB-200 (600M distilled) | 200 langs | via pivot mostly | fair | fast | CC-BY-NC ⚠️ |
| NLLB-200 (1.3B/3.3B) | 200 langs | via pivot | fair–good | heavier | CC-BY-NC ⚠️ |

**Recommendation:** **IndicTrans2 distilled (200M)** as default MT, upgrade to 1B if quality matters and VRAM allows. Keep NLLB only if you need a language IndicTrans2 lacks.

---

## 4. Source-vs-output-language design — the three mechanisms

Wisper picks one of three paths per dictation based on (source language, output language):

**Mechanism 1 — Transcribe in source language (ASR only).**
`audio → ASR(transcribe, lang=source) → text(source)`
Use when **output == source**. Simplest path, one model, no MT. E.g. Hindi→Hindi, English→English, Kannada→Kannada.

**Mechanism 2 — Whisper built-in translate task.**
`audio → Whisper(translate) → text(English)`
Use *only* when **output == English** and source is a language Whisper translates well. One model pass, no separate MT stage. Cheapest way to get English out. **Cannot** target any non-English language. For weak-source langs (Kannada) prefer Mechanism 3 instead, because you're leaning on Whisper's weak Kannada understanding.

**Mechanism 3 — ASR → dedicated local MT.**
`audio → ASR(transcribe, lang=source) → text(source) → MT(source→target) → text(target)`
Use for **any non-English target**, and for **English target when source ASR is weak** (transcribe with a strong Indic ASR, then translate with IndicTrans2 — usually beats Whisper's own translate for Kannada). Handles arbitrary pairs (Hindi→Kannada, English→Hindi). Two stages, more latency/VRAM, most flexible.

Rule of thumb: **Mechanism 1 for same-language, Mechanism 2 only for the cheap English case, Mechanism 3 for everything else and whenever ASR quality of the source is weak.**

---

## 5. MT model choice (summary)

Default to **IndicTrans2 distilled (200M)** for all translation. It:
- covers every source/target pair we care about (En, Hi, Kn + 19 more Indic),
- does Indic→Indic **directly** (critical for Hindi→Kannada without English pivot),
- is permissively licensed,
- is small enough to co-reside with an ASR model on a consumer NVIDIA GPU.

Upgrade to IndicTrans2-1B for quality. Reserve NLLB-200 for non-Indic, non-English targets only (and accept its non-commercial license).

---

## 6. Recommended routing table

Source (rows) × Output (columns). Cell = mechanism + engine.

| Speak ↓ / Paste → | **English** | **Hindi** | **Kannada** | **Other Indic** |
|---|---|---|---|---|
| **English** | M1: Whisper `large-v3` | M3: Whisper ASR → IndicTrans2 (En→Hi) | M3: Whisper ASR → IndicTrans2 (En→Kn) | M3: Whisper ASR → IndicTrans2 |
| **Hindi** | M2: Whisper `translate` *(or M3 for higher quality)* | M1: Whisper `large-v3` / IndicWhisper | M3: IndicWhisper → IndicTrans2 (Hi→Kn) | M3: IndicWhisper → IndicTrans2 |
| **Kannada** | **M3**: IndicConformer/IndicWhisper → IndicTrans2 (Kn→En) *(not M2 — Whisper's Kannada is weak)* | M3: Indic ASR → IndicTrans2 (Kn→Hi) | **M1: IndicConformer / IndicWhisper** *(not vanilla Whisper)* | M3: Indic ASR → IndicTrans2 |
| **Other Indic** | M2 if Whisper is strong for it, else M3 | M3: Indic ASR → IndicTrans2 | M3: Indic ASR → IndicTrans2 | M1 if same lang; else M3 |
| **Hinglish (mixed)** | M2 (Whisper→English) or M1 keep-mixed | M1 Whisper keep-mixed → optional normalize | M3 (normalize to Hindi first) | — |

Notes:
- "M1" = same-language ASR. "M2" = Whisper translate (English-only). "M3" = ASR→IndicTrans2.
- Diagonal (same source & target) is always M1 — cheapest, no MT.
- Anything landing in the English column from a *strong-ASR* source can use M2 for simplicity; from a *weak-ASR* source (Kannada), use M3 with a good Indic ASR front-end.
- Off-diagonal non-English targets are always M3 with IndicTrans2.

---

## 7. Code-switching / Hinglish

Real Indian speech mixes English into Hindi/Kannada constantly ("Hinglish").

- **Whisper handles mixed speech reasonably** in `transcribe` mode — it was trained on some code-switched audio and will keep English words as English and Hindi as Devanagari (or romanized, depending). This makes **Mechanism 1 with Whisper the best default for capturing Hinglish faithfully** (keep-mixed).
- **Indic-only models (IndicConformer)** and **MT (IndicTrans2)** expect cleaner monolingual input and can mishandle heavy mixing. So: do **not** force mixed audio straight into IndicTrans2.
- If the user wants a **single clean output language** from Hinglish input: transcribe with Whisper (keep-mixed) first, then optionally run MT to normalize the whole thing to one language. Accept that mid-sentence switches degrade MT quality.
- Practical default: for a user whose profile is "Hindi (allows English)", transcribe with Whisper and **paste as-is (mixed)** unless they explicitly chose a single target language.

---

## 8. Scripts & romanization

- **Hindi → Devanagari** by default. **Kannada → Kannada script** by default. ASR/MT models emit native script natively.
- **Romanized (Latin) output** is an optional post-processing step, not a model choice:
  - Use a transliteration library — AI4Bharat **IndicXlit** (Indic transliteration) or the `indic-transliteration` Python package — to convert Devanagari/Kannada → Latin after ASR/MT.
  - Offer it as a per-profile toggle: "output in Latin script".
- Romanized **input** (user speaks Hindi but wants Latin out) is just: transcribe in native script → transliterate to Latin. Don't try to make the ASR emit Latin directly.
- Keep script conversion as the **last** stage (after any MT), so MT always operates on native script it was trained on.

---

## 9. Language-selection behavior (behavior only)

Recommended defaults — reliability over cleverness:

- **Manual + remembered per profile is the default.** Store `{source_lang, target_lang, output_script}` per user profile. Most users dictate in a stable language pair; asking once beats mis-detecting every time.
- **Auto-detect as opt-in / fallback.** Whisper's language auto-detect is fine for high-resource langs but unreliable for short clips and low-resource Indic langs (exactly Kannada, where errors are costly). Offer "auto-detect source" as a toggle, not the default.
- **Output language is always explicit.** There is no way to infer intended target from audio, so target is always a chosen setting (defaulting to "same as source").
- **Quick-switch hotkey / profile switch** so a bilingual user can flip between, say, "Hindi→Hindi" and "Hindi→English" without opening settings.
- **Confidence-based fallback:** if auto-detect confidence is low, fall back to the profile's remembered source language rather than trusting the guess.

---

## 10. Assumptions & open questions (for synthesis)

Assumptions:
- Single consumer NVIDIA GPU; VRAM budget must hold ASR + (sometimes) MT simultaneously. IndicTrans2-distilled + Whisper `large-v3` should co-fit on ~8–12 GB; tune with quantization if not.
- Batch/offline-per-utterance is acceptable (hotkey toggle → whole transcript pasted), so two-stage M3 latency is tolerable — we're not streaming.
- Free/open + permissive licensing preferred → favors IndicTrans2 over NLLB.

Open questions:
- Exact current WER for Whisper `large-v3` vs IndicWhisper vs IndicConformer on Hindi/Kannada FLEURS — **needs a live benchmark run**; numbers here are directional/unverified (2026).
- Whether shipping *two* ASR backends (Whisper for English/Hindi/Hinglish + IndicConformer for South-Indian) is worth the integration cost vs. IndicWhisper-only.
- Best Hinglish normalization strategy when the user demands a single output language — likely needs empirical testing.
- Model load/swap policy: keep MT resident vs. load-on-demand, given per-dictation latency targets.
- Whether the distilled IndicTrans2 quality is sufficient, or 1B is needed for Indic→Indic pairs.

---

## Sources

Web search was unavailable during authoring; the following are the primary references to verify against (from prior knowledge, not re-fetched):

- OpenAI Whisper (model card / repo) — task types (`transcribe` vs English-only `translate`), language list, `large-v3`.
- AI4Bharat — IndicWhisper, IndicConformer/IndicASR, IndicTrans2, IndicXlit (ai4bharat.org / Hugging Face `ai4bharat/*`).
- Meta AI — NLLB-200 (model card, CC-BY-NC license note).
- NVIDIA NeMo — Conformer ASR toolkit underlying IndicConformer.
- FLEURS benchmark — for Indic ASR WER comparisons (to be run to replace unverified numbers).
