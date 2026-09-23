# 06 — Text Formatting & Cleanup

_Wisper: fully local, free alternative to Wispr Flow. Windows 11 + NVIDIA CUDA. Multilingual (English, Hindi, Kannada, other Indic)._

This document covers the stage that runs **after** the raw transcript arrives and **before** it is pasted at the cursor: turning a messy spoken transcript into clean text without changing what the user meant.

---

## 1. Requirements & the two modes

The pipeline is: user speaks → presses hotkey to stop → raw transcript → **cleanup** → paste at cursor.

Two cleanup modes, plus an on-demand button.

| Mode | Default? | What it does | What it must NOT do |
|------|----------|--------------|---------------------|
| **LIGHT** (disfluency removal) | ✅ Default | Remove fillers (um, uh, "like", "you know", Hindi/Kannada equivalents), collapse stutters, drop immediate repeated words, drop false starts. Normalize punctuation + capitalization. | No paraphrase, no synonym swaps, no reordering, no grammar "fixes", no meaning changes. **Keep the user's exact wording.** |
| **POLISH / REWRITE** | ❌ Opt-in only | Everything LIGHT does, plus fix grammar and improve clarity/flow. | Change meaning, add facts, translate, or invent content. Must stay faithful. |
| **Refresh / Optimize button** | On demand | Re-run cleanup on current text, or escalate LIGHT → POLISH on the visible text. | (Inherits the guarantees of whichever pass it runs.) |

Everything is local. No network calls. No cloud.

### The core promise
LIGHT mode is the product's trust anchor. If the default silently rewrote the user's words, they could never trust dictation for names, code, commands, quotes, or non-native phrasing. **LIGHT = "delete noise, touch nothing else."**

---

## 2. Why word-swapping must not be the default

Wispr-style tools that aggressively rewrite feel magical for casual prose and infuriating for everything else. Reasons word-swapping is opt-in, never default:

- **Fidelity is a feature.** Names ("Kaveri", "Bengaluru"), technical terms, code identifiers, filenames, and exact quotes must survive verbatim. A synonym swap here is a bug.
- **Multilingual = higher risk.** An LLM asked to "improve" Hindi/Kannada text tends to translate, transliterate, or "correct" perfectly valid dialect/code-switching. Users mixing English + Indic ("matlab I think we should…") are exactly the people a rewrite hurts most.
- **Trust compounds.** One surprise edit and the user stops trusting the paste. Reversibility is weak once text is already pasted into another app.
- **Determinism.** A rule-based delete-only pass has zero hallucination surface. That is impossible to guarantee from a generative model, only bound.

So: **default is deterministic + delete-only. Anything generative or meaning-altering is a deliberate, visible opt-in.**

---

## 3. Rule-based fast cleanup (the default engine)

A pure-Python, deterministic pass. Zero model latency, zero hallucination, runs in well under a millisecond for typical utterances. This is the **instant default** and the strongest guarantee of "keep my exact words".

Stages, in order:

1. **Per-language filler removal.** Match filler tokens/phrases against a per-language dictionary (see §7). Remove as whole tokens only (word boundaries), never as substrings — "umbrella" must not lose "um".
2. **Stutter collapse.** Collapse repeated leading fragments of the same word: `th- th- the` → `the`; `I-I-I` → `I`. Detect via a hyphen/repetition heuristic and prefix-of-next-word matching.
3. **Immediate-repeat collapse.** `the the cat` → `the cat`; `is is` → `is`. Only collapse **adjacent** duplicates (optionally across one filler that was just removed). Do **not** dedupe non-adjacent repeats — "very very good" and legitimately repeated words stay.
4. **False-start heuristic.** Drop an abandoned fragment before a restart cue. Conservative: only when a short leading clause is followed by a clear restart of the same subject, e.g. "I went — I mean I drove to…". Bias toward under-removing; a missed false start is harmless, a wrongly deleted clause is not.
5. **Whitespace + punctuation normalization.** Collapse multiple spaces, fix space-before-punctuation, ensure single space after punctuation, join stray commas left by removed fillers.
6. **Capitalization.** Capitalize sentence starts and standalone "I" (English only). Leave Indic scripts untouched (no case). If Whisper already supplied punctuation/casing, prefer light touch-ups over re-doing it.

Design rules:
- **Delete-only.** The output is always a subsequence of the input tokens (plus punctuation/whitespace edits). This is the machine-checkable invariant that proves nothing was paraphrased.
- **Configurable aggressiveness.** Filler lists and the false-start heuristic behind small toggles, so users can dial it down.
- Dictionaries live in editable data files (one per language), not hardcoded, so users can add regional fillers.

---

## 4. LLM-based cleanup (model choice + Ollama)

For higher-quality LIGHT cleanup and for the POLISH pass, use a **small local LLM via Ollama** (already the recommended local-model runner on Windows/CUDA; no new infra). The rule-based pass stays the default; the LLM is refinement on demand or an optional inline upgrade.

### Candidate small models
Sizes/behaviour below are **unverified (2026)** — treat as a starting shortlist, benchmark on-device before committing.

| Model | Approx size | Notes | Multilingual (Hindi/Kannada) |
|-------|-------------|-------|------------------------------|
| **Qwen2.5-3B** | ~3B | Strong instruction-following at small size; good multilingual coverage. Good default candidate. | Comparatively strong |
| **Llama-3.2-3B** | ~3B | Solid general instruction model; lighter Indic coverage. | Moderate |
| **Gemma-2-2B** | ~2B | Smallest/fastest; fine for English light cleanup. | Weaker on Indic |
| **Phi-3.5-mini** | ~3.8B | Good reasoning/instruction adherence; English-leaning. | Moderate |

Recommendation: start with **Qwen2.5-3B** (instruction-following + best Indic coverage of the shortlist), quantized (e.g. Q4_K_M) to fit comfortably in VRAM and keep latency low. Fall back to Gemma-2-2B if latency on the target GPU is too high.

Ollama call sketch (local, no network):

```bash
ollama pull qwen2.5:3b
```

```python
import requests

def llm_clean(text: str, prompt: str, model="qwen2.5:3b") -> str:
    r = requests.post("http://localhost:11434/api/generate", json={
        "model": model,
        "prompt": prompt.format(text=text),
        "stream": False,
        "options": {"temperature": 0.0, "top_p": 1.0, "num_predict": 512},
    }, timeout=30)
    return r.json()["response"].strip()
```

Key options: **`temperature: 0.0`** (deterministic, minimizes creative rewriting), tight `num_predict`, no system-level "be helpful/creative" nudges.

---

## 5. Prompt templates (light vs polish)

Use these verbatim. Keep them terse; every extra sentence is a chance for the model to over-help.

### (a) LIGHT — disfluency-only

```
You clean up dictated speech. Remove ONLY these from the text:
- filler words (um, uh, er, like, you know, so, matlab, haan, yaani, and similar)
- stutters and repeated fragments (e.g. "th- th- the" -> "the")
- immediately repeated words (e.g. "the the" -> "the")
- abandoned false starts (a fragment the speaker restarts)

Rules:
- Do NOT paraphrase. Do NOT swap any word for a synonym.
- Do NOT fix grammar. Do NOT reorder words. Do NOT translate.
- Keep every remaining word EXACTLY as written, in the same language.
- Only add/normalize punctuation and capitalization.
- Return ONLY the cleaned text. No quotes, no notes, no explanation.

Text:
{text}
```

### (b) POLISH — grammar/clarity, faithful to meaning

```
You lightly edit dictated speech into clean written text.
- Remove fillers, stutters, repeats, and false starts.
- Fix grammar, punctuation, and capitalization.
- Improve clarity and flow ONLY where it does not change the meaning.

Rules:
- Stay faithful to the original meaning. Add no new information.
- Do NOT translate. Keep the original language(s), including code-switching.
- Preserve names, technical terms, numbers, and quoted text exactly.
- Return ONLY the edited text. No notes, no explanation.

Text:
{text}
```

---

## 6. The refresh / optimize button

A single button on the transcript/result surface. Behaviour:

- **First press (default state):** re-run the current mode. If LIGHT is active and only the rule-based pass ran, escalate to the **LLM LIGHT** pass on the current visible text.
- **Second press / long-press / menu:** run **POLISH** on the current text.
- Idempotent-ish: operates on whatever text is currently shown, so the user can iterate (paste → optimize → optimize again for a stronger pass) without re-recording.
- Always **non-destructive in-place**: keep the previous version for one-step undo. Because POLISH can change wording, undo here is essential.
- Runs entirely locally; shows a small spinner if the LLM pass takes more than ~150 ms.

State machine (visible text is the single source of truth):

```
raw ──rule LIGHT──▶ pasted   ──[Optimize]──▶ LLM LIGHT ──[Optimize again]──▶ POLISH
                      ▲                                                        │
                      └──────────────────── undo ──────────────────────────---┘
```

---

## 7. Multilingual filler handling

Fillers are per-language and must be removed **without translating** the surrounding text. Whisper itself already drops some fillers and supplies punctuation, so cleanup should be additive, not a re-transcription.

| Language | Common fillers (non-exhaustive) |
|----------|--------------------------------|
| English | um, uh, er, hmm, like, you know, I mean, sort of, kind of, basically, actually, so, well, right |
| Hindi | matlab (मतलब), haan (हाँ), yaani (यानी), toh (तो), achha (अच्छा), bas (बस), waise (वैसे), kya bolun |
| Kannada | andre (ಅಂದ್ರೆ), haudu (ಹೌದು), matte (ಮತ್ತೆ), enaythu, haage (ಹಾಗೆ), sari (ಸರಿ) |

Notes and cautions:
- Store one editable dictionary per language, with both **script** and **romanized** forms (users dictate romanized Hindi/Kannada constantly).
- **Context matters.** "so", "actually", "right", "toh", "matlab", "sari" are also real content words. Prefer removing them only in clear filler positions (utterance start, or between clauses surrounded by pauses/commas). When unsure, keep. Over-removal changes meaning; the whole point is to avoid that.
- **Never translate or transliterate.** Cleanup operates within the detected language; it does not convert Devanagari→Latin or Kannada→English.
- **Code-switching is normal.** A single utterance may mix English + Hindi + Kannada. Run all relevant filler lists but keep every non-filler token in its original script.
- Detect language(s) from the Whisper output (it already reports language) and load the matching dictionaries; when mixed, union them.

---

## 8. Latency strategy

Goal: text appears to paste **instantly**, quality improves on demand.

| Path | Approx latency | When |
|------|----------------|------|
| Rule-based LIGHT | < 1 ms | Always, immediately — this is what gets pasted first |
| LLM LIGHT (3B, Q4, CUDA) | ~100–400 ms est. | Inline if fast enough on target GPU, else on Optimize |
| LLM POLISH (3B, Q4, CUDA) | ~200–800 ms est. | Optimize button only |

_All LLM figures are rough estimates for a short utterance on a mid-range NVIDIA GPU; measure on the actual device._

Recommended flow:
1. **Paste the rule-based result immediately.** Zero perceived latency, guaranteed word-faithful.
2. Keep the model **warmed** (Ollama keeps it resident; send a tiny priming request at app start) so the first optimize press isn't cold-start slow.
3. If on-device LLM LIGHT measures fast enough (say < 200 ms) to feel instant, offer an option to run it inline instead of (or right after) the paste — but the deterministic paste always happens first so nothing blocks the cursor.
4. POLISH is never on the hot path; it's always an explicit button.

---

## 9. Guardrails against paraphrase / hallucination in LIGHT mode

The rule-based pass is safe by construction (delete-only). The **LLM LIGHT** pass needs bounding, because a model can always drift. Layered defenses:

1. **Deterministic decoding.** `temperature: 0.0`, no sampling creativity.
2. **Constrained prompt.** Explicit "do not paraphrase / synonym / translate / reorder", "return only cleaned text" (see §5a).
3. **Post-check: subsequence / overlap test.** After the LLM returns, verify the output is (close to) a **subsequence of the input tokens**. Concretely:
   - Tokenize input and output (case-fold, strip punctuation for the check).
   - Confirm every output token appears in the input in order (allowing removals only, no insertions).
   - Compute token-overlap ratio; require e.g. ≥ 0.95 of output tokens present in input.
4. **Divergence → reject → fall back.** If the LLM output inserts new words, reorders, or drops too much (overlap below threshold), **discard it and keep the rule-based result**. The user is never shown an unverified rewrite in LIGHT mode.
5. **No such check on POLISH** (it's allowed to change words), but POLISH still gets a lighter guard: reject if output length differs wildly from input (a sign of runaway generation) or if language changed.

Minimal self-check for the subsequence invariant (the one piece of non-trivial logic worth pinning):

```python
def is_light_faithful(original: str, cleaned: str, min_overlap=0.95) -> bool:
    """LIGHT output must be (nearly) a token-subsequence of the input: deletions only."""
    def toks(s):
        return [t for t in ''.join(c.lower() if c.isalnum() or c.isspace() else ' '
                                   for c in s).split()]
    src, out = toks(original), toks(cleaned)
    if not out:
        return False
    i, matched = 0, 0
    for w in out:                      # greedy in-order match against source
        while i < len(src) and src[i] != w:
            i += 1
        if i < len(src):
            matched += 1
            i += 1
    return matched / len(out) >= min_overlap

if __name__ == "__main__":
    # deletions only -> faithful
    assert is_light_faithful("um I I think the the cat sat", "I think the cat sat")
    # synonym swap -> rejected
    assert not is_light_faithful("I think the cat sat", "I believe the feline sat")
    # inserted/new content -> rejected
    assert not is_light_faithful("open the door", "please open the front door now")
    print("ok")
```

If `is_light_faithful` returns False, use the rule-based output instead.

---

## 10. Assumptions & open questions for synthesis

**Assumptions:**
- Ollama is the local model runner (consistent with the rest of the project on Windows/CUDA); no new dependency introduced for LLM cleanup.
- Whisper output already includes language tag and basic punctuation; cleanup refines rather than re-punctuates from scratch.
- A 2–3B quantized model fits comfortably in the target GPU's VRAM alongside the ASR model, or is loaded on demand.

**Open questions:**
- Can LLM LIGHT run inline (< ~200 ms) on the target GPU, or is it strictly an Optimize-button feature? Needs on-device measurement.
- VRAM budget: can ASR + a 3B LLM be resident simultaneously, or must one be swapped (adding cold-start latency)?
- Best default filler aggressiveness for Indic code-switching — needs real user transcripts to tune (risk of removing content words like "toh", "matlab", "sari").
- Should the Optimize button expose LIGHT-vs-POLISH explicitly, or auto-escalate on repeated presses (as sketched in §6)?
- Undo depth: single-step is proposed; is multi-step history worth it?

---

## 11. Sources

All content here is **general knowledge**, written without web access.
- Model names, sizes, and behaviours (Qwen2.5-3B, Llama-3.2-3B, Gemma-2-2B, Phi-3.5-mini) are **unverified (2026)** — a shortlist to benchmark, not a current leaderboard.
- Latency figures are **estimates**, not measurements; confirm on the target NVIDIA GPU.
- Filler-word lists are illustrative and non-exhaustive; expand from real user data.
