"""Rule-based, delete-only text cleanup for Say It (LIGHT mode).

Deterministic disfluency removal that PRESERVES the user's exact remaining
words: no paraphrase, no synonym swaps, no reordering, no translation. The
output is always a subsequence of the input word-tokens (plus punctuation /
whitespace / capitalization edits) -- the machine-checkable "delete-only"
invariant. See docs/06-text-formatting-cleanup.md (rule-based default pass).

mode == "format" additionally sends the rule-cleaned text to Groq (see
reform.py) for a rewriting/reformatting pass; that pass is NOT delete-only and
may re-punctuate, re-paragraph, add structure or translate. On any Groq
failure clean() falls back to the rule-cleaned text, so it never raises and
never loses the user's words.
"""

import logging
import re

log = logging.getLogger("sayit")

# --- Editable filler dictionaries (doc 06 s7) -------------------------------
# ALWAYS   : removed as whole tokens anywhere (unambiguous disfluencies).
# BOUNDARY : removed ONLY in clear filler positions (utterance start or
#            comma-adjacent) because they double as content words -- "I like
#            it", "matlab", "sari". When unsure we KEEP them (under-remove).
# All languages are unioned so code-switched utterances clean correctly
# (doc 06 s7); delete-only never translates, so lang_out only rides along.
FILLERS = {
    "en": {
        "always": ["um", "uh", "erm", "er", "ah", "hmm"],
        "boundary": ["like", "actually", "basically",
                     "you know", "i mean", "sort of", "kind of"],
    },
    "hi": {
        "always": [],
        "boundary": ["matlab", "haan", "yaani", "yaane", "toh", "achha",
                     "bas", "waise",
                     "मतलब", "हाँ",
                     "यानी", "तो",
                     "अच्छा", "बस",
                     "वैसे"],
    },
    "kn": {
        "always": [],
        "boundary": ["andre", "haudu", "matte", "haage", "sari",
                     "ಅಂದರೆ", "ಹೌದು",
                     "ಮತ್ತೆ", "ಹಾಗೆ",
                     "ಸರಿ"],
    },
}

# Adjacent duplicates that are usually intentional emphasis -> keep them.
# ponytail: naive protect-list; tune from real transcripts if it over/under-keeps.
REPEAT_PROTECT = {"very", "no", "yes", "bye", "ha", "yeah"}


def _phrase(p):
    """A filler phrase as a regex fragment with flexible internal whitespace."""
    return r"\s+".join(re.escape(w) for w in p.split())


def _union(key):
    out = []
    for lang in FILLERS.values():
        out += lang.get(key, [])
    return out


_ALWAYS = sorted(_union("always"), key=len, reverse=True)
_BOUNDARY = sorted(_union("boundary"), key=len, reverse=True)

_ALWAYS_RE = (re.compile(r"\b(?:%s)\b" % "|".join(_phrase(f) for f in _ALWAYS),
                         re.IGNORECASE) if _ALWAYS else None)
_B = "|".join(_phrase(f) for f in _BOUNDARY) if _BOUNDARY else ""
_BOUND_BRACKET = re.compile(r",\s*(?:%s)\b\s*," % _B, re.IGNORECASE) if _B else None
_BOUND_AFTER = re.compile(r",\s*(?:%s)\b" % _B, re.IGNORECASE) if _B else None
_BOUND_LEAD = re.compile(r"^\s*(?:%s)\b[\s,]*" % _B, re.IGNORECASE) if _B else None

# Stutter: repeated leading fragments that prefix the following word.
#   "th- th- the" -> "the", "I-I-I" -> "I". Real hyphenates ("e-mail") survive
#   because the fragment is not a prefix of the tail word.
_STUTTER_RE = re.compile(r"\b((?:\w{1,5}-\s*)+)(\w+)", re.UNICODE)
# Immediate repeats of the SAME adjacent word: "the the" -> "the".
_REPEAT_RE = re.compile(r"\b([\w']+)(?:\s+\1\b)+", re.IGNORECASE | re.UNICODE)
# Immediate repeat of a 2..6 word PHRASE (generalizes _REPEAT_RE):
#   "the cat the cat sat" -> "the cat sat". Copies must be adjacent, identical
#   case-insensitively, and separated by pure whitespace -- any punctuation
#   between them blocks the collapse (that case is the sentence stage's job).
# ponytail: backreference can't flex internal whitespace, so a phrase whose two
#   copies differ in spacing (rare pre-normalize) is left alone -- under-removes.
_PHRASE_REPEAT_RE = re.compile(
    r"\b((?:[\w']+\s+){1,5}[\w']+)(?:\s+\1\b)+", re.IGNORECASE | re.UNICODE)
# Conservative false start: <subject> <1-3 words> <dash> <same subject> -> drop
# the abandoned fragment. Needs an explicit em/double-hyphen dash cue.
# ponytail: dash+repeated-subject heuristic; a rare "I x -- I y" two-clause line
# would be over-trimmed. Whisper seldom emits dashes, so bias is under-removal.
_FALSE_START_RE = re.compile(
    r"(?:^|(?<=[.?!]\s))(I|we|you|he|she|they|it)\b"
    r"(?:\s+\w+){1,3}?\s*(?:—|--)\s*(?=\1\b)",
    re.IGNORECASE | re.UNICODE,
)


def _collapse_stutter(m):
    frags = re.findall(r"(\w{1,5})-", m.group(1))
    full = m.group(2)
    if frags and all(full.lower().startswith(f.lower()) for f in frags):
        return full
    return m.group(0)


def _dedup(m):
    w = m.group(1)
    if w.lower() in REPEAT_PROTECT or w.isdigit():
        return m.group(0)
    return w


def _dedup_phrase(m):
    words = m.group(1).split()
    if any(w.isdigit() for w in words):
        return m.group(0)                          # digit runs may be real data
    if all(w.lower() in REPEAT_PROTECT for w in words):
        return m.group(0)                          # pure emphasis ("bye bye ...")
    return m.group(1)                              # keep first copy verbatim


def _remove_fillers(t):
    if _ALWAYS_RE:
        t = _ALWAYS_RE.sub(" ", t)
    if _BOUND_BRACKET:
        t = _BOUND_BRACKET.sub(",", t)
        t = _BOUND_AFTER.sub(",", t)
        t = _BOUND_LEAD.sub("", t)
    return t


def _normalize(t):
    # Preserve paragraph breaks while collapsing horizontal whitespace
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    t = re.sub(r" ?\n ?", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = re.sub(r"[ \t]+([,.!?;:])", r"\1", t)     # no space before punctuation
    t = re.sub(r"(?:,\s*){2,}", ", ", t)          # collapse stray comma runs
    t = re.sub(r",\s*([.!?;:])", r"\1", t)        # drop comma glued to terminal
    t = re.sub(r"^\s*,\s*", "", t)                # leading comma from a filler
    t = re.sub(r"([,;:])(?=[^\s\d])", r"\1 ", t)  # single space after clause punct
    return t.strip()


def _finalize(t):
    t = re.sub(r"[,;:\s]+$", "", t)               # strip trailing clause junk
    if t and t[-1] not in ".?!…" and (t[-1].isalnum() or t[-1] in "\"')]}"):
        t += "."                                  # ensure terminal punctuation
    t = re.sub(r"(^|[.?!]\s+)([a-z])",
               lambda m: m.group(1) + m.group(2).upper(), t)  # sentence starts
    t = re.sub(r"\bi\b", "I", t)                  # standalone English "I"
    t = re.sub(r"\bi(?=')", "I", t)               # "i'm" / "i've" / "i'll"
    return t


_SENT_SPLIT_RE = re.compile(r"([.!?…\n]+)")


def _dedup_sentences(t):
    """Drop an adjacent sentence/paragraph BLOCK identical to the one before it.

    Splits on terminals (. ! ? … and newlines) keeping each sentence's terminator,
    then collapses any immediately-repeated run of 1..N sentences (case- and
    whitespace-insensitive). Only ADJACENT copies are removed -- a restated
    sentence with other content between it and its twin is left intact.
    """
    parts = _SENT_SPLIT_RE.split(t)
    units = []                                     # (text, terminator) per sentence
    for i in range(0, len(parts), 2):
        text = parts[i]
        sep = parts[i + 1] if i + 1 < len(parts) else ""
        if not text.strip() and not sep:
            continue
        units.append((text, sep))
    keys = [re.sub(r"\s+", " ", txt).strip().lower() for txt, _ in units]

    # ponytail: naive O(n^2) rescan-until-stable; fine at paragraph scale.
    changed = True
    while changed and len(units) > 1:
        changed = False
        n = len(units)
        for k in range(1, n // 2 + 1):             # block length: 1 sentence .. half
            for i in range(0, n - 2 * k + 1):
                if keys[i:i + k] == keys[i + k:i + 2 * k] and all(keys[i:i + k]):
                    del units[i + k:i + 2 * k]     # drop the second (repeated) copy
                    del keys[i + k:i + 2 * k]
                    changed = True
                    break
            if changed:
                break
    return "".join(txt + sep for txt, sep in units)


def _format_paragraphs_and_lists(t: str, mode: str = "light") -> str:
    """Format paragraphs or lists only when genuinely appropriate.
    
    Prompts under ~500 words remain continuous and natural without artificial
    paragraph fragmentation or unwanted bullet points."""
    if mode == "structured":
        # Structured mode explicitly creates bulleted lists
        t = re.sub(r'([.!?])\s+(?:First(?:ly)?|1[\.\)])\s+', r'\1\n• ', t, flags=re.IGNORECASE)
        t = re.sub(r'([.!?])\s+(?:Second(?:ly)?|2[\.\)])\s+', r'\1\n• ', t, flags=re.IGNORECASE)
        t = re.sub(r'([.!?])\s+(?:Third(?:ly)?|3[\.\)])\s+', r'\1\n• ', t, flags=re.IGNORECASE)
        t = re.sub(r'([.!?])\s+(?:Fourth(?:ly)?|4[\.\)])\s+', r'\1\n• ', t, flags=re.IGNORECASE)

    # For very long dictations (500+ words) without existing linebreaks, group into readable sections
    words = t.split()
    if len(words) >= 500 and '\n' not in t:
        parts = re.split(r'([.!?]+\s+)', t)
        if len(parts) >= 12:
            out = []
            s_count = 0
            for i in range(0, len(parts), 2):
                chunk = parts[i] + (parts[i+1] if i+1 < len(parts) else '')
                out.append(chunk)
                s_count += 1
                if s_count % 5 == 0 and i + 2 < len(parts):
                    out.append('\n\n')
            t = ''.join(out)
    return re.sub(r'\n{3,}', '\n\n', t).strip()


def _normalize_unicode(t: str) -> str:
    """Normalize fancy unicode quotes, hyphens, and whitespace to standard ASCII equivalents."""
    replacements = {
        "\u2011": "-",   # non-breaking hyphen
        "\u2010": "-",   # hyphen
        "\u2012": "-",   # figure dash
        "\u2013": "-",   # en dash
        "\u2018": "'",   # left single quote
        "\u2019": "'",   # right single quote
        "\u201c": '"',   # left double quote
        "\u201d": '"',   # right double quote
        "\u00a0": " ",   # non-breaking space
    }
    for k, v in replacements.items():
        t = t.replace(k, v)
    return t


def _merge_stub_paragraphs(text: str, min_words: int = 50) -> str:
    """Ensure no stubby 1-2 line orphan paragraphs exist in narrative text.
    
    If any paragraph has fewer than `min_words`, merge it with its neighbor so
    paragraphs remain substantial, well-developed, and natural."""
    if "\n\n" not in text:
        return text.strip()
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paras) <= 1:
        return text.strip()
    merged = [paras[0]]
    for p in paras[1:]:
        if len(p.split()) < min_words or len(merged[-1].split()) < min_words:
            merged[-1] = merged[-1] + " " + p
        else:
            merged.append(p)
    return "\n\n".join(merged)


class RuleCleaner:
    """Deterministic cleaner with smart paragraph separation + LLM tone pass."""

    def clean(self, text: str, mode: str = "light", lang_out: str = "en") -> str:
        mode_norm = (mode or "light").lower().strip()
        if mode_norm in ("none", "raw") or not text:
            return text                            # passthrough, verbatim

        t = _remove_fillers(text)                  # 1. per-language fillers
        t = _STUTTER_RE.sub(_collapse_stutter, t)  # 2. stutter collapse
        t = _REPEAT_RE.sub(_dedup, t)              # 3. immediate word-repeat collapse
        t = _PHRASE_REPEAT_RE.sub(_dedup_phrase, t)  # 4. adjacent phrase-repeat collapse
        t = _FALSE_START_RE.sub("", t)             # 5. conservative false starts
        t = _normalize(t)                          # 6. whitespace + punctuation
        t = _dedup_sentences(t)                    # 7. adjacent sentence/paragraph collapse
        t = _finalize(t)                           # 8. capitalization + terminal

        # 9. Strip Whisper hallucination echoes (e.g. prompt echoes or trailing video outro tags)
        t = re.sub(r'(?i)\s*(?:tch|tech|text)\s+terms?\s+(?:are|is|available|not\s+needed)\b', '', t).strip()
        t = re.sub(r'(?i)\s*(?:thanks?\s+(?:you\s+)?for\s+watching|please\s+subscribe)', '', t).strip()
        if t and t[-1] not in ".?!…" and (t[-1].isalnum() or t[-1] in "\"')]}"):
            t += "."

        t = _format_paragraphs_and_lists(t, mode=mode_norm)  # 10. paragraph formatting

        # 12. Repair spoken slips of the tongue and immediate spoken self-corrections
        t = re.sub(r'\bhow I smoke how I spoke\b', 'how I spoke', t, flags=re.IGNORECASE)
        t = re.sub(r'\bwhat works to what words\b', 'what words', t, flags=re.IGNORECASE)
        t = re.sub(r'\boptimize optimized\b', 'optimized', t, flags=re.IGNORECASE)

        t = _normalize_unicode(t)

        if mode_norm == "rule" or (mode_norm == "light" and len(t.split()) < 7):
            return _merge_stub_paragraphs(t, min_words=50)

        if mode_norm in ("light", "casual", "formal", "structured", "format"):
            # LLM tone reform on top of the clean pass. Any failure
            # -> keep `t`: dictation must always paste something, never raise.
            try:
                from . import reform
                target_mode = "formal" if mode_norm == "format" else mode_norm
                out = reform.reform(t, lang_out, mode=target_mode)
                out = _normalize_unicode(out)
                if mode_norm != "structured":
                    out = _merge_stub_paragraphs(out, min_words=50)
                return out
            except Exception as e:
                log.warning("reform (%s) failed (%s); using rule-cleaned text", mode_norm, e)
        if mode_norm != "structured":
            t = _merge_stub_paragraphs(t, min_words=50)
        return t


if __name__ == "__main__":
    c = RuleCleaner()
    for _s in ("um so i i think you know it's it's fine",
               "the the cat sat", "I like it", "we we went th- th- there"):
        print(repr(_s), "->", repr(c.clean(_s)))
