# 04 — Audio Capture Without Artifacts (Windows-first)

> **Status:** research/design. Written from domain knowledge; the web gateway was
> down during authoring, so external specifics are labeled **unverified (2026)**.
> This is the project's #1 reliability concern — see [[project-wisper]].

## The requirement

Capture the microphone for speech-to-text **without disturbing any other audio on the
system**. The bug that plagues open-source dictation tools and that Wisper must NOT have:

- Background music/Spotify/YouTube volume **drops** the instant recording starts.
- A game or call's audio **cuts out** or gets "thin"/artifacted.
- The mic signal itself is mangled (AGC pumping, aggressive noise suppression) so the
  transcript accuracy drops.

None of these are inherent to recording a mic. They are all caused by *how* the capture
stream is opened. Open it correctly and other audio is completely untouched.

---

## Root causes and the fix for each

| # | Root cause | Symptom | Fix |
|---|------------|---------|-----|
| a | Mic opened under the Windows **communications role** (`eCommunications`) | Other apps' audio auto-ducked (lowered ~80%) | Don't request the comms role; set the OS Communications ducking policy to "Do nothing" |
| b | WASAPI **exclusive mode** | Other apps lose the device / go silent | Use **shared mode** only |
| c | Sample-rate / format mismatch | Clicks, warble, resample glitches | Negotiate the device's native mix format, resample cleanly to 16 kHz mono |
| d | Driver "audio enhancements" / **AGC** / noise-suppression / echo-cancel | Mic signal pumps, breathes, or over-suppresses → worse WER | Capture raw; do our own light processing; document how to disable enhancements |

### (a) The ducking one — the big one

Windows has an **automatic ducking** ("stream attenuation") feature. When *any*
application opens an audio stream flagged as a **communications** stream, the OS applies
the user's "Communications activity" policy to *every other* stream on the system.
Default policy on many machines = **"Reduce the volume of other sounds by 80%."** That is
exactly the "my music disappeared" bug.

The trigger is the **device role / stream category**, not "recording" itself:

- Win32 endpoint role `eCommunications` (vs `eConsole` / `eMultimedia`).
- WASAPI session category `AudioCategory_Communications` (vs `_Other`, `_Media`).

**Fix (two layers, do both):**

1. **Open the capture stream as a normal/console/media stream, never as communications.**
   - With **PortAudio/sounddevice** on WASAPI: open the *default input device by its
     device index* (not a "communications default"), in shared mode. PortAudio's WASAPI
     host API opens shared render/capture without the comms category by default. Do **not**
     use any comms/loopback-comms flag. *(exact `WasapiSettings` flag names: unverified (2026) — validate against the installed PortAudio build.)*
   - For **full control**, open the client natively via **comtypes/pycaw** (WASAPI
     `IAudioClient`) and set the session category to `AudioCategory_Other` (or `_Media`),
     never `_Communications`. This is the only way to be 100% certain of the category; the
     PortAudio path is simpler and usually sufficient.
2. **Neutralize the OS ducking policy** so even if something else opens a comms stream,
   Wisper's presence doesn't cause ducking, and Wisper's own capture never does:
   - Guide the user (Settings → System → Sound → *More sound settings* →
     **Communications** tab → **"Do nothing"**), and/or
   - Set it programmatically via the registry/Core Audio ducking API on first run, with
     the user's consent. Registry: `HKCU\Software\Microsoft\Multimedia\Audio` →
     `UserDuckingPreference = 3` (3 = "Do nothing"). *(value semantics unverified (2026) — confirm before shipping an auto-set; default to *guiding* the user, not silently editing their registry.)*

> **Design decision:** ship with the **"guide the user + open as non-comms"** approach by
> default. Auto-editing the ducking registry key is opt-in (a one-click "fix ducking"
> button), because silently changing a system-wide audio policy is a surprising side effect.

### (b) Shared vs exclusive mode

- **Shared mode:** the audio engine mixes Wisper's capture with everyone else. Multiple
  apps use the device simultaneously. **This is what we want.**
- **Exclusive mode:** the app takes sole ownership of the endpoint at a specific format;
  other apps are pushed off it. Lower latency, but it's antisocial and causes the
  "everything else went silent" bug. **Never use it for a background dictation tool.**

PortAudio/sounddevice default to shared mode; just don't request exclusive.

### (c) Sample rate / format / resampling

- Whisper-family models want **16 kHz, mono, float32** (or int16 → float).
- The device's shared-mode mix format is often **44.1 or 48 kHz**. Opening the stream at
  a rate the device doesn't natively run forces a resample somewhere; doing it wrong (or
  letting a mismatched callback run) causes glitches.
- **Approach:** open the capture stream at the **device's native mix rate**, then resample
  to 16 kHz mono ourselves with a good resampler (`soxr` — high quality, or
  `scipy.signal.resample_poly`, or librosa). One clean, controlled resample. Mono downmix
  by averaging channels. This avoids driver/engine resample surprises and is deterministic.
- Alternatively let sounddevice open directly at 16 kHz if the device advertises support;
  fall back to native-rate + our resample if not.

### (d) Harmful DSP: AGC, noise suppression, echo cancel, "enhancements"

- Windows per-device **"Audio enhancements"** and vendor driver DSP (Realtek/Nvidia
  Broadcast/etc.) can apply AGC and aggressive denoise. These are tuned for calls, not
  transcription, and can pump/over-suppress → worse WER and audible artifacts in monitoring.
- **Approach:** capture as raw as the stack allows. We do our own light work:
  - **VAD** (Silero) for endpointing, not noise gating of the signal we send to STT.
  - Optional mild high-pass / normalization only if measured to help.
- **Document** how users disable enhancements (Sound settings → device properties →
  Advanced / "Audio enhancements: Off") for best accuracy, but don't require it — Whisper
  is fairly robust. Do **not** ship our own AGC on by default.

---

## Recommended capture library & configuration

**Library:** `sounddevice` (PortAudio bindings) as the primary — mature, cross-platform,
callback-based, gives us WASAPI shared capture without the comms role. Keep a native
WASAPI-via-`comtypes`/`pycaw` path in reserve only if we ever need to force the session
category explicitly.

**Config (baseline):**

- Host API: WASAPI (Windows), **shared mode**, **non-communications** device.
- Open at device native rate (e.g. 48 kHz), or 16 kHz if directly supported.
- Channels: capture native, downmix to **mono**.
- Callback / blocksize: small fixed block (e.g. 20–30 ms, ~480–960 frames at 16 kHz) fed
  into a **ring buffer**; never do heavy work in the audio callback.
- Convert/resample to **16 kHz mono float32** on a worker thread, not in the callback.

---

## VAD (Silero) integration

- Run **Silero VAD** on the 16 kHz stream to detect speech/silence.
- Uses in Wisper:
  1. Trim leading/trailing silence before handing audio to STT (faster, cleaner).
  2. Segment for the optional background-incremental transcription path (see
     [[01-architecture-and-pipeline]]).
- VAD is for *endpointing/segmentation*, **not** for gating or altering the audio we
  transcribe — we don't want to clip quiet speech.

---

## Buffering / threading for zero dropouts

```
[WASAPI shared capture]
   → audio callback thread  (only: copy frames into a lock-free/locked ring buffer)
   → capture worker thread  (drain ring buffer → downmix → resample to 16k → append to utterance buffer; run VAD)
   → STT worker thread      (on stop: transcribe the full utterance buffer)
```

Rules:
- The audio callback does **the minimum**: copy samples out, return. No resample, no VAD,
  no allocation spikes → no xruns/dropouts.
- Ring buffer sized for a comfortable margin (e.g. a few hundred ms) so a scheduling hiccup
  never drops frames.
- Backpressure: if a worker stalls, we drop *nothing* from the utterance (memory is cheap
  for a spoken paragraph); we only ever drop from the tiny RT ring if truly overrun, and we
  log it.

---

## Coexisting with other capture apps

Shared-mode capture means Discord/Zoom/OBS can read the same mic at the same time. We do
**not** grab exclusive access and do **not** change the default device. If the user records
in another app while Wisper is idle, nothing changes. When Wisper records, it just adds one
more shared reader.

---

## Device selection & permissions

- Enumerate input devices; let the user pick (default = system default input, resolved by
  device index, **not** the communications default).
- Windows 11 microphone privacy: the app must have mic permission
  (Settings → Privacy → Microphone). Detect denial and surface a clear message rather than
  failing silently.

---

## Verification / test plan (proves the bug is gone)

1. **Ducking test:** Play music (Spotify/browser) at a fixed volume. Start Wisper
   recording. **Assert:** music volume does **not** change (measure the render peak meter
   before/after, or just listen). Stop recording — still unchanged.
2. **Coexistence test:** Join a call / run OBS capturing the same mic; start Wisper.
   **Assert:** the other app keeps receiving mic audio; no device-lost error.
3. **Artifact test:** Record a known phrase over background music; **assert** no dropouts,
   clicks, or warble in the captured 16 kHz wav (visual + listen).
4. **Enhancement test:** Toggle "Audio enhancements" on/off; compare WER on a fixed clip to
   confirm our raw-capture recommendation.
5. **Rate-negotiation test:** Force a 44.1 kHz device and a 48 kHz device; confirm clean
   16 kHz output both ways.

Automate 1 + 3 as the regression gate before any release.

---

## Portability notes (brief)

- **macOS:** CoreAudio via PortAudio; there is no equivalent global "communications
  ducking" bug, but respect `AVAudioSession`-style categories in any native path; mic TCC
  permission required.
- **Linux:** PulseAudio/PipeWire via PortAudio; open a normal capture stream (don't request
  a "phone"/comms role). PipeWire mixes cleanly with other streams by default.
- The ducking problem is **Windows-specific**; the shared-mode + native-rate + our-resample
  design is identical everywhere.

---

## Assumptions & open questions for synthesis

- Exact PortAudio `WasapiSettings` flag names and whether the installed build exposes
  session-category control — **verify against the actual dependency**; fall back to the
  `pycaw`/`comtypes` native path if not.
- `UserDuckingPreference` registry value semantics — **unverified (2026)**; default to
  *guiding* the user rather than silently editing it.
- Whether we need the native WASAPI path at all, or PortAudio's default non-comms shared
  capture is sufficient in practice (likely sufficient — validate on real hardware).

## Sources

General domain knowledge (WASAPI shared/exclusive modes, endpoint roles `eConsole`/
`eMultimedia`/`eCommunications`, WASAPI session categories, Windows stream-attenuation/
ducking, PortAudio/sounddevice, Silero VAD). External URLs not fetched (gateway down at
authoring); **verify the flag/registry specifics above before implementation.**
