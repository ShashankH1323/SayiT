"""Integration tests for Wisper Flow Light Mode.

Tests:
1. Cross-prompt deduplication (repeats in 1st half and 2nd half unified seamlessly).
2. Prompts < 500 words do not have artificial paragraph breaks or bullet points.
3. Contextual phonetic correction (e.g. Canada -> Kannada in language context).
4. Hallucination stripping (trailing 'Thanks for watching', prompt echo 'Tch terms...').
5. Natural conversational tone preservation without AI corporate rewriting.
"""

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sayit.clean import RuleCleaner


def load_env():
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("GROQ_API_KEY="):
                os.environ["GROQ_API_KEY"] = line.split("=", 1)[1].strip()


def main():
    load_env()
    cleaner = RuleCleaner()

    # 1. Hallucination & prompt echo removal (rule level)
    raw_with_echo = (
        "So we have to link it in GitHub. Thanks for watching. "
        "Tch terms are available in the description Text terms are not needed. Tch terms are the same."
    )
    cleaned_echo = cleaner.clean(raw_with_echo, mode="rule")
    assert "thanks for watching" not in cleaned_echo.lower(), f"Outro survived: {cleaned_echo}"
    assert "tch terms" not in cleaned_echo.lower(), f"Prompt echo survived: {cleaned_echo}"
    assert "text terms" not in cleaned_echo.lower(), f"Prompt echo survived: {cleaned_echo}"
    assert "github" in cleaned_echo.lower(), f"Content lost: {cleaned_echo}"
    print("Test 1 (Hallucination & echo removal): PASSED")

    # 2. RuleCleaner paragraph suppression under 500 words
    short_text = (
        "First, I think we should check the database. Also, the API needs an update. "
        "Secondly, we should test the authentication flow. However, let's keep it simple."
    )
    rule_out = cleaner.clean(short_text, mode="rule")
    assert "\n\n" not in rule_out, f"Unwanted paragraphs in short text: {rule_out!r}"
    assert "•" not in rule_out, f"Unwanted bullet point in light mode: {rule_out!r}"
    print("Test 2 (No artificial paragraphs/bullets in short text): PASSED")

    # 3. Groq Reform Light Mode (if key available)
    if not os.environ.get("GROQ_API_KEY"):
        print("GROQ_API_KEY not set; skipping live Groq reform tests.")
        return

    # 3A. Cross-prompt deduplication test
    # Speaker talks about auth token in first half, talks about UI, then repeats auth token in second half
    dedup_input = (
        "So today I want to work on the login screen. We need to make sure the authentication token "
        "is saved properly in secure storage. Then afterwards we can look at the dashboard UI and maybe "
        "style the navigation bar. But wait, coming back to the login screen, like I said earlier, we "
        "definitely have to ensure the auth token is saved in secure storage, that is really critical. "
        "And then we can test the whole flow."
    )
    out_dedup = cleaner.clean(dedup_input, mode="light")
    low_dedup = out_dedup.lower()
    # Should contain secure storage / auth token once, not repeated twice as separate duplicate sentences
    auth_mentions = len(re.findall(r"secure storage", low_dedup))
    assert auth_mentions == 1, f"Expected 1 mention of secure storage, got {auth_mentions}: {out_dedup}"
    assert "login screen" in low_dedup, "Login screen context lost"
    assert "dashboard" in low_dedup, "Dashboard context lost"
    assert "\n\n" not in out_dedup, f"Short prompt split into paragraphs: {out_dedup}"
    assert "•" not in out_dedup, f"Bullet points in light mode: {out_dedup}"
    print("Test 3 (Cross-prompt deduplication & flow): PASSED")
    print(f"   -> Result:\n   {out_dedup}\n")

    # 3B. Indian language / phonetic context test
    phonetic_input = (
        "Main bol raha tha ki we should support Canada language also because South India mein "
        "Kannada speakers bahut hain, and STT should recognize it properly."
    )
    out_phonetic = cleaner.clean(phonetic_input, mode="light")
    assert "Canada" not in out_phonetic, f"'Canada' was not corrected to 'Kannada': {out_phonetic}"
    assert "Kannada" in out_phonetic, f"'Kannada' missing: {out_phonetic}"
    print("Test 4 (Phonetic context correction): PASSED")
    print(f"   -> Result:\n   {out_phonetic}\n")

    # 3C. User's exact prompt from history
    user_prompt_input = (
        "The above prompt itself I guess we did a lot of formatting and all I guess the prompt itself now "
        "changed I don't feel like I have spoken that and then when I read back the prompt it should feel like "
        "I have okay I have spoken all this and I should I have only told all this it should not be look like "
        "okay this has been like really like oh this is refreshed too much and it's like too much strictness "
        "in the prompt it should be Accuracy matters but overall prompt like the accuracy the word detection "
        "those matters but it's okay if you can't rephrase it really well understanding the context but I prefer "
        "you have to do it you have to do it such naturally that it should feel like the user has given all the prompt "
        "and like do not use the paragraph system and separation system Use it only when the prompt is getting too "
        "large like one page and all. Like for small prompts like 500 words, 1000 words, 2000 words. I don't think you "
        "need to use this paragraph system and all. It looks odd and then the prompt looks very different because when it "
        "separated it has become more readable So when we read that we feel like I haven spoken it like that The prompt "
        "has been changed or I did not speak that way."
    )
    out_user = cleaner.clean(user_prompt_input, mode="light")
    assert "•" not in out_user, f"Bullet points in user prompt: {out_user}"
    assert len(out_user.split()) > 50, "Output suspiciously truncated"
    # 3D. User's latest raw vs Wispr Flow test case
    raw_user_speech = (
        "So, yeah, so what do we do is that now I will give you some words like I will speak some like 500 words "
        "and say you that how we are going to do it. I mean, I will give you the raw things that I speak and I will "
        "give you the whisper which will optimize optimized paragraph or optimized output and see so we'll you will "
        "have an example of how I smoke how I spoke and how whisper did correct that and then you will also have "
        "accuracies like you have to detect the words and then remove those so you will understand how the contextual "
        "analysis works as well so you will understand what works to what words to remove and what words to not remove "
        "and all so let me just also like read a paragraph as well so also there will be like some I mean if I read a "
        "paragraph it will be obvious that I'll be reading the words which are there but if I say something then it's "
        "different right so I have to say it by myself so let's see now I'll like it's a minute of talking so now I "
        "don't know how many words have been spoken but I think it should be enough so you could test probably "
        "everything out and we'll actually know the output of the model I mean output of the raw and the whisper so "
        "I don't want the output to be raw that's one thing because yeah so yeah you get it now you get what to do "
        "now you have raw output and then we got this whisper output so I think yes we are done so yeah"
    )
    out_flow = cleaner.clean(raw_user_speech, mode="light")
    assert "•" not in out_flow, f"Bullet points in output: {out_flow}"
    assert "smoke" not in out_flow.lower(), f"Speech slip survived: {out_flow}"
    assert "what works to what words" not in out_flow.lower(), f"Speech slip survived: {out_flow}"
    assert "so, yeah, so" not in out_flow.lower(), f"Throat clearing survived: {out_flow}"
    assert "500 words" in out_flow, f"Number formatting altered: {out_flow}"
    paragraphs = [p.strip() for p in out_flow.split("\n\n") if p.strip()]
    for p in paragraphs:
        assert len(p.split()) >= 40, f"Found stubby 1-2 line paragraph ({len(p.split())} words): {p!r}"
    print("Test 6 (Wispr Flow comparative raw test - no stub paragraphs): PASSED")
    print(f"   -> Result:\n{out_flow}\n")

    # 3E. Long multi-topic dictation test (substantial paragraphs)
    long_multi_topic = (
        "Let us talk about the backend infrastructure architecture. We are migrating our entire service "
        "layer from legacy microservices to a unified API gateway. All authentication tokens will now be verified "
        "at the edge using lightweight cryptographic signatures. This will dramatically reduce latency and eliminate "
        "cascading failures across our internal service mesh. The database connection pools have also been tuned to "
        "handle high concurrent spikes during peak hours.\n\n"
        "Turning our attention now to the customer onboarding experience, the product team has completely redesigned "
        "the signup flow. New users will now go through a frictionless three-step setup wizard that guides them "
        "through account creation, team invites, and workspace configuration. User testing has shown a fifty percent "
        "drop in abandonment rates with this new streamlined interface. We expect to roll this out to all beta users "
        "starting next Monday morning."
    )
    out_multi = cleaner.clean(long_multi_topic, mode="light")
    multi_paras = [p.strip() for p in out_multi.split("\n\n") if p.strip()]
    assert len(multi_paras) >= 2, f"Expected multi-topic to keep paragraphs: {out_multi}"
    for p in multi_paras:
        assert len(p.split()) >= 40, f"Paragraph too short: {p}"
    print("Test 7 (Long multi-topic substantial paragraphs): PASSED")
    print(f"   -> Result:\n{out_multi}\n")

    print("ALL LIGHT MODE TESTS PASSED!")


if __name__ == "__main__":
    main()
