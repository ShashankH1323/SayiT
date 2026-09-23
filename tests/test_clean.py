"""Self-test for the rule-based delete-only cleaner. Run: python tests/test_clean.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wisper.clean import RuleCleaner


def main() -> None:
    _cleaner = RuleCleaner()
    # Use mode="rule" so unit tests verify deterministic rules offline
    class _C:
        def clean(self, s, mode="rule"):
            return _cleaner.clean(s, mode=mode)
    c = _C()

    # 1) full disfluency sweep: fillers gone, doubles collapsed, cased, terminated
    out = c.clean("um so i i think you know it's it's fine")
    low = out.lower()
    assert "um" not in low.split(), f"filler 'um' survived: {out!r}"
    assert "you know" not in low, f"'you know' survived: {out!r}"
    assert "i i" not in low, f"doubled 'i' survived: {out!r}"
    assert "it's it's" not in low, f'doubled "it\'s" survived: {out!r}'
    assert out[:1].isupper(), f"sentence not capitalized: {out!r}"
    assert out.rstrip().endswith("."), f"no terminal punctuation: {out!r}"
    assert "think" in low and "fine" in low, f"content word lost: {out!r}"
    assert out == "So I think it's fine.", f"unexpected result: {out!r}"

    # 2) immediate repeat of a determiner collapses
    out = c.clean("the the cat sat")
    assert "the cat" in out.lower(), f"'the cat' missing: {out!r}"
    assert "the the" not in out.lower(), f"'the the' survived: {out!r}"

    # 3) mode='none' is verbatim passthrough
    raw = "um the the RAW  text ,unchanged"
    assert c.clean(raw, mode="none") == raw, "mode='none' must return input unchanged"

    # 4) idempotency: cleaning twice == cleaning once
    for s in ("um so i i think you know it's it's fine",
              "the the cat sat",
              "I like it",
              "we we went th- th- there",
              "I went -- I drove to work"):
        once = c.clean(s)
        assert c.clean(once) == once, \
            f"not idempotent: {s!r} -> {once!r} -> {c.clean(once)!r}"

    # 5) a real content word ('like' as a verb) is NOT removed
    out = c.clean("I like it")
    low = out.lower()
    assert low.startswith("i "), f"subject 'I' lost: {out!r}"
    assert "like" in low, f"verb 'like' wrongly removed: {out!r}"
    assert "it" in low.replace(".", " ").split(), f"object 'it' lost: {out!r}"

    # 6) conservative false start (explicit dash + repeated subject) is trimmed
    out = c.clean("I went -- I drove to work")
    assert "went" not in out.lower(), f"false start not trimmed: {out!r}"
    assert "drove to work" in out.lower(), f"restart clause lost: {out!r}"

    # 7) adjacent multi-word PHRASE dedup collapses the repeated n-gram
    out = c.clean("the cat the cat sat")
    assert out == "The cat sat.", f"phrase dedup failed: {out!r}"
    out = c.clean("I think I think we should go")
    assert out == "I think we should go.", f"phrase dedup failed: {out!r}"

    # 8) a single duplicated sentence collapses to one
    out = c.clean("the cat sat. the cat sat.")
    assert out == "The cat sat.", f"sentence dedup failed: {out!r}"

    # 9) a duplicated multi-sentence paragraph collapses to one copy
    para = ("the meeting is at noon. bring your laptop. "
            "the meeting is at noon. bring your laptop.")
    out = c.clean(para)
    assert out == "The meeting is at noon. Bring your laptop.", \
        f"paragraph dedup failed: {out!r}"

    # 10) idempotency holds for the new stages too
    for s in ("the cat the cat sat",
              "I think I think we should go",
              "the cat sat. the cat sat.",
              para):
        once = c.clean(s)
        assert c.clean(once) == once, \
            f"not idempotent: {s!r} -> {once!r} -> {c.clean(once)!r}"

    # 11) NEGATIVE: ordinary text, non-adjacent repeats, and protected emphasis
    #     are all left intact (only casing/terminal punctuation added).
    out = c.clean("the cat sat on the mat and the dog ran in the park")
    assert out == "The cat sat on the mat and the dog ran in the park.", \
        f"ordinary text altered: {out!r}"
    out = c.clean("i saw a bird. then i saw a plane. i saw a bird.")
    assert out.lower().count("i saw a bird") == 2, \
        f"non-adjacent sentence repeat destroyed: {out!r}"
    out = c.clean("bye bye bye bye")
    assert out.lower().count("bye") == 4, \
        f"protected emphasis destroyed: {out!r}"

    print("clean self-test PASSED")


if __name__ == "__main__":
    main()
