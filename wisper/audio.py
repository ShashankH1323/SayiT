"""Audio capture for Wisper: WASAPI shared, non-communications, artifact-free.

Core reliability feature (doc 04): we open the mic in WASAPI *shared* mode and
NEVER under the communications role, so recording does not duck/mute other apps'
audio. PortAudio's WASAPI host API opens shared, non-comms by default; we just
avoid exclusive mode and any comms flag. We capture at the device's native rate
in a minimal callback, then do one clean downmix + resample to 16 kHz mono
ourselves (avoids driver/engine resample glitches).

Imports of soxr/sounddevice are guarded so this module imports and to_mono /
resample work with numpy alone.
"""
from __future__ import annotations

import logging
import threading

import numpy as np

log = logging.getLogger("wisper")

try:
    import soxr as _soxr
except Exception:  # pragma: no cover - optional high-quality resampler
    _soxr = None

try:
    import sounddevice as _sd
except Exception:  # pragma: no cover - optional; start() will explain if missing
    _sd = None


# WDM-KS excluded everywhere: unreliable here (PaErrorCode -9999 WdmSyncIoctl) and
# PortAudio may hand us one via the raw system default. Shared with AudioCapture so
# the host API a mic is listed under is the one it gets opened on.
_PREFERRED_HOSTAPIS = ("WASAPI", "MME", "DirectSound")

# Generic Windows mapper pseudo-devices: not real mics, one per host API.
_GENERIC_INPUT_NAMES = ("Microsoft Sound Mapper - Input", "Primary Sound Capture Driver")


def _hostapi_rank(api_name: str) -> int:
    """Rank of the first _PREFERRED_HOSTAPIS entry matching api_name (lower = preferred)."""
    for i, pref in enumerate(_PREFERRED_HOSTAPIS):
        if pref in api_name:
            return i
    return len(_PREFERRED_HOSTAPIS)


def list_input_devices() -> list[tuple[str, int]]:
    """[(label, device_index), ...] for input-capable devices, one entry per mic name.

    PortAudio lists each mic once per host API; we dedup by name, keeping the
    copy on the earliest _PREFERRED_HOSTAPIS (WASAPI first) -- the UI keys on the
    name and AudioCapture re-resolves it the same way, so the listed index is the
    one opened. WDM-KS and the generic Windows mapper pseudo-devices are dropped;
    if that leaves nothing we fall back to the raw input list so the user always
    has a mic to pick. Labels read "Microphone (Pebble Comet) — Windows WASAPI".
    Empty list if sounddevice is unavailable.
    """
    if _sd is None:
        return []
    hostapis = _sd.query_hostapis()
    base: list[tuple[str, int]] = []            # fallback: every input, WDM-KS excluded
    best: dict[str, tuple[int, str, int]] = {}  # name -> (rank, label, idx), deduped
    for idx, d in enumerate(_sd.query_devices()):
        if d["max_input_channels"] <= 0:
            continue
        api = hostapis[d["hostapi"]]["name"]
        if "WDM-KS" in api:
            continue
        label = f"{d['name']} — {api}"
        base.append((label, idx))
        if d["name"] in _GENERIC_INPUT_NAMES:
            continue
        rank = _hostapi_rank(api)
        prev = best.get(d["name"])
        if prev is None or rank < prev[0]:
            best[d["name"]] = (rank, label, idx)
    deduped = [(label, idx) for _, label, idx in best.values()]
    return deduped or base  # never hand back an empty list when inputs exist


def refresh_input_devices() -> list[tuple[str, int]]:
    """Re-initialize PortAudio backend to detect newly plugged-in/removed devices,
    then return the fresh list_input_devices()."""
    global _sd
    if _sd is not None:
        try:
            _sd._terminate()
            _sd._initialize()
        except Exception as e:
            log.warning("error reinitializing sounddevice: %s", e)
    return list_input_devices()


def to_mono(pcm: np.ndarray) -> np.ndarray:
    """(n,) or (n, ch) -> (n,) float32. Multi-channel is averaged."""
    pcm = np.asarray(pcm, dtype=np.float32)
    if pcm.ndim == 1:
        return pcm
    if pcm.ndim == 2:
        return pcm.mean(axis=1, dtype=np.float32)
    raise ValueError(f"expected 1-D or 2-D audio, got shape {pcm.shape!r}")


def resample(pcm: np.ndarray, orig_sr: int, target_sr: int = 16000) -> np.ndarray:
    """Mono float32 @orig_sr -> mono float32 @target_sr.

    Uses soxr (high quality) when importable, else numpy linear interpolation.
    """
    pcm = np.asarray(pcm, dtype=np.float32)
    if orig_sr == target_sr or pcm.size == 0:
        return pcm.astype(np.float32, copy=False)
    if _soxr is not None:
        return np.asarray(_soxr.resample(pcm, orig_sr, target_sr), dtype=np.float32)
    # ponytail: numpy linear-interp fallback; upgrade path is soxr (already tried above).
    n_out = int(round(pcm.shape[0] * target_sr / orig_sr))
    if n_out <= 0:
        return np.zeros(0, dtype=np.float32)
    x_new = np.linspace(0.0, pcm.shape[0] - 1, n_out)
    return np.interp(x_new, np.arange(pcm.shape[0]), pcm).astype(np.float32)


class AudioCapture:
    """Records the mic via WASAPI shared / non-communications and returns
    float32 mono @ ``samplerate`` on :meth:`stop`."""

    def __init__(self, samplerate: int = 16000, device: int | str | None = None):
        self.samplerate = int(samplerate)
        # device: None -> auto; str -> mic name substring (stable across replug);
        # int -> legacy device index (honored unless missing/WDM-KS).
        self.device = device
        self._stream = None
        self._frames: list[np.ndarray] = []
        self._recording = False
        self._native_sr: int | None = None
        self.xruns = 0  # count of callback status flags (overruns), for logging
        self._last_ok_device: int | None = None  # index that last opened cleanly
        self._monitoring = False
        self._monitor_stream = None
        self._monitor_level = 0.0
        # pywebview runs every JS->Python call on its own thread, so start/stop
        # preview can race. Unserialized, two starts each open a stream and one
        # is orphaned: still capturing, unstoppable, and its PortAudio callback
        # crashes the process once Python frees it. RLock: start_monitor calls
        # stop_monitor.
        self._monitor_lock = threading.RLock()

    def _pick_explicit(self, hostapis, devices) -> int | None:
        """Resolve an explicit :attr:`device` to a live input index, else None.

        ``str`` -> first input-capable device whose name contains the substring
        (case-insensitive), searched in preferred host-API order so WDM-KS is
        never matched. ``int`` -> that index, honored unless it is out of range,
        not an input, or a WDM-KS device. Returning None means "fall back to
        auto" (never crash on a stale pin). Recomputed at start() time.
        """
        if isinstance(self.device, str):
            want = self.device.lower()
            for pref in _PREFERRED_HOSTAPIS:
                for idx, d in enumerate(devices):
                    if d["max_input_channels"] <= 0:
                        continue
                    if pref not in hostapis[d["hostapi"]]["name"]:
                        continue
                    if want in d["name"].lower():
                        return idx
            log.warning("audio: no input device matches name %r; using auto", self.device)
            return None
        idx = int(self.device)
        if not (0 <= idx < len(devices)) or devices[idx]["max_input_channels"] <= 0:
            log.warning("audio: device index %d is not a live input; using auto", idx)
            return None
        if "WDM-KS" in hostapis[devices[idx]["hostapi"]]["name"]:
            log.warning("audio: device index %d is WDM-KS; using auto", idx)
            return None
        return idx

    def _input_candidates(self) -> list[int]:
        """Input device indices to try, in preferred host-API order, never WDM-KS.

        An explicit :attr:`device` (name substring or legacy index) is resolved
        live via :meth:`_pick_explicit` and tried first; a missing/WDM-KS pin is
        dropped so it can't poison the list. The auto candidates always follow:
        for each of :attr:`_PREFERRED_HOSTAPIS` (WASAPI -> MME -> DirectSound)
        that host API's ``default_input_device`` (console/media default, never
        the comms default), or its first input-capable device when no default is
        set. Only if none of the preferred APIs is present do we fall back to
        PortAudio's raw system default. So a stale pin degrades to auto instead
        of crashing.
        """
        hostapis = _sd.query_hostapis()
        devices = _sd.query_devices()
        out: list[int] = []
        if self.device is not None:
            picked = self._pick_explicit(hostapis, devices)
            if picked is not None:
                out.append(picked)
        for pref in _PREFERRED_HOSTAPIS:
            for hi, h in enumerate(hostapis):
                if pref not in h["name"]:
                    continue
                di = h.get("default_input_device", -1)
                if di is not None and di >= 0:
                    out.append(int(di))
                else:  # host API present but no default set -> scan its inputs
                    for idx, d in enumerate(devices):
                        if d["hostapi"] == hi and d["max_input_channels"] > 0:
                            out.append(idx)
                            break
        if not out:  # no preferred host API available; last resort
            di = int(_sd.default.device[0])
            # Never hand back a WDM-KS device (or an unset -1 default): the app
            # excludes WDM-KS everywhere. Skipping it leaves out empty, so
            # start() raises a clear "no usable input device" (BUG 1).
            if (0 <= di < len(devices)
                    and "WDM-KS" not in hostapis[devices[di]["hostapi"]]["name"]):
                out.append(di)
        seen: set[int] = set()  # dedupe, preserve order
        return [x for x in out if not (x in seen or seen.add(x))]

    def _resolve_input(self) -> int:
        """First preferred input device (see :meth:`_input_candidates`)."""
        return self._input_candidates()[0]

    def _callback(self, indata, frames, time_info, status) -> None:
        # Minimum work only (doc 04): copy the block out, return. No resample,
        # no VAD, no heavy allocation -> no xruns/dropouts.
        if status:
            self.xruns += 1
        self._frames.append(indata.copy())

    def start(self) -> None:
        if _sd is None:
            raise RuntimeError(
                "sounddevice is not installed; cannot capture audio. "
                "Install it (`pip install sounddevice`) to enable AudioCapture; "
                "to_mono/resample work without it."
            )
        if self._recording:
            return
        if self._monitoring:
            self.stop_monitor()
        self._frames = []
        self.xruns = 0
        # Try each candidate host API in order; some (e.g. WDM-KS if it ever
        # sneaks in, or a busy device) raise PortAudioError on open/start. This
        # is the hardware-reality knob: different machines expose different
        # working APIs, so we fall through to the next rather than crashing.
        # Try the last-known-good device first (skips a device that failed on a
        # prior start()), then the normal candidate order for resilience.
        # ponytail: in-memory per instance -> resets each app run; a device that
        # unplugs mid-session just fails here and falls back again. Acceptable.
        candidates = self._input_candidates()
        if self._last_ok_device is not None:
            candidates = [self._last_ok_device] + candidates
        seen: set[int] = set()  # dedupe, preserve order
        candidates = [d for d in candidates if not (d in seen or seen.add(d))]
        last_err: Exception | None = None
        for dev in candidates:
            try:
                self._open_stream(dev)
            except Exception as e:
                # Broad on purpose: ANY failure (not just PortAudioError) must
                # release a partially-opened device before the next candidate,
                # or the mic stays locked until the process restarts (BUG 1).
                last_err = e
                log.warning("audio: device %d failed to open (%s); trying next", dev, e)
                self._close_stream()
                continue
            self._last_ok_device = dev
            self._recording = True
            return
        if last_err is None:  # candidates was empty -> never `raise None`
            raise RuntimeError("no usable input device")
        raise last_err  # every candidate failed

    def _open_stream(self, dev: int) -> None:
        info = _sd.query_devices(dev, "input")
        self._native_sr = int(round(info["default_samplerate"]))
        # Capture native channels, capped at 2 (mics are mono/stereo); downmixed later.
        channels = min(max(1, int(info["max_input_channels"])), 2)
        hostapi_name = _sd.query_hostapis(info["hostapi"])["name"]
        # WasapiSettings() with all-False flags == shared mode, non-communications
        # role. Only attach it on the WASAPI host API (portable elsewhere).
        extra = None
        if "WASAPI" in hostapi_name and hasattr(_sd, "WasapiSettings"):
            extra = _sd.WasapiSettings()  # exclusive=False -> shared, non-comms
        self._stream = _sd.InputStream(
            device=dev,
            channels=channels,
            samplerate=self._native_sr,
            dtype="float32",
            blocksize=int(self._native_sr * 0.03),  # ~30 ms block
            callback=self._callback,
            extra_settings=extra,
        )
        try:
            self._stream.start()
        except BaseException:
            # InputStream(...) already OPENED the device; if start() (or anything
            # after construction) fails, close it here or the device leaks (BUG 1).
            self._close_stream()
            raise
        log.info("audio: capturing on %s (device %d, %d Hz)", hostapi_name, dev, self._native_sr)

    def _close_stream(self) -> None:
        """Stop + close the input stream and drop the reference, if any. Safe to
        call repeatedly and on a partially-opened / already-stopped stream:
        errors from a double stop/close are swallowed so the device is always
        released (BUG 1)."""
        s, self._stream = self._stream, None
        if s is None:
            return
        try:
            s.stop()
        except Exception:
            log.debug("audio: stream.stop() during close raised", exc_info=True)
        try:
            s.close()
        except Exception:
            log.debug("audio: stream.close() during close raised", exc_info=True)

    def stop(self) -> np.ndarray:
        """Stop capture; return float32 mono @ self.samplerate in ~[-1, 1].
        Idempotent: safe when no stream is open or after a prior stop()."""
        self._close_stream()
        self._recording = False
        frames, self._frames = self._frames, []
        if not frames:
            return np.zeros(0, dtype=np.float32)
        raw = np.concatenate(frames, axis=0)  # (n,) or (n, ch)
        mono = to_mono(raw)
        out = resample(mono, self._native_sr or self.samplerate, self.samplerate)
        return np.ascontiguousarray(out, dtype=np.float32)

    def preprocess_for_stt(self, pcm, samplerate, noise_suppression=False, input_threshold=0.0):
        """Optional pre-STT cleanup: silence gate + gentle noise suppression.

        ``pcm`` is float32 mono @ ``samplerate``; returns float32 mono @ same rate.
        The default path (no suppression, no threshold) returns ``pcm`` unchanged --
        zero cost, zero accuracy impact. A clip whose RMS is below ``input_threshold``
        returns an empty array to signal "silence, skip STT".
        """
        # Default: nothing requested -> identity, untouched (hot path).
        if not noise_suppression and input_threshold <= 0:
            return pcm
        pcm = np.asarray(pcm, dtype=np.float32)
        if pcm.size == 0:
            return pcm
        # Silence gate: drop clips quieter than the threshold entirely.
        if input_threshold > 0:
            rms = float(np.sqrt(np.mean(np.square(pcm))))
            if rms < input_threshold:
                return np.zeros(0, dtype=np.float32)
        if not noise_suppression:
            return pcm
        # ponytail: naive numpy amplitude noise-gate -- noise floor from the
        # quietest ~10% of short-frame RMS, then a soft linear ramp that only
        # attenuates frames below ~1.75x that floor (speech frames stay at gain
        # 1.0). Deliberately gentle: over-denoising hurts Whisper. Upgrade to
        # RNNoise / spectral subtraction if quality demands.
        frame = max(1, int(samplerate * 0.02))  # ~20 ms frames
        n = pcm.shape[0]
        n_frames = int(np.ceil(n / frame))
        pad = n_frames * frame - n
        padded = np.concatenate([pcm, np.zeros(pad, dtype=np.float32)]) if pad else pcm
        env = np.sqrt(np.mean(np.square(padded.reshape(n_frames, frame)), axis=1) + 1e-12)
        floor = float(np.percentile(env, 10.0))            # noise floor ~ quietest 10%
        thresh = floor * 1.75                              # ~1.5-2x floor
        gain = np.ones(n_frames, dtype=np.float32)
        quiet = env < thresh                               # only frames in the floor band
        gain[quiet] = 0.15 + 0.85 * (env[quiet] / (thresh + 1e-12))  # soft ramp, ==1 at thresh
        if n_frames >= 3:                                  # smooth so gain steps don't click
            gain = np.convolve(gain, np.array([0.25, 0.5, 0.25], np.float32), mode="same")
        centers = np.arange(n_frames) * frame + frame / 2.0
        per_sample = np.interp(np.arange(n), centers, gain).astype(np.float32)  # click-free
        return (pcm * per_sample).astype(np.float32)

    def is_recording(self) -> bool:
        return self._recording

    def _monitor_callback(self, indata, frames, time_info, status) -> None:
        if indata.size:
            # Remove DC offset to prevent static bias from reading as speech
            zero_mean = indata - np.mean(indata)
            cur = float(np.abs(zero_mean).max())
            # Noise gate: ignore ambient floor / background mic hiss
            noise_gate = 0.015
            if cur < noise_gate:
                cur = 0.0
            else:
                cur = min(1.0, (cur - noise_gate) / (0.35 - noise_gate))
            # Smooth peak with slight decay so 60ms UI polling reliably captures voice peaks
            self._monitor_level = max(cur, self._monitor_level * 0.82)
        else:
            self._monitor_level = 0.0

    def start_monitor(self, device=None) -> None:
        """Open a lightweight, non-recording input stream for device preview / UI waveform."""
        with self._monitor_lock:
            if _sd is None or self._recording:
                return
            self.stop_monitor()
            old_dev = self.device
            if device is not None:
                self.device = device
            try:
                candidates = self._input_candidates()
                if not candidates:
                    return
                dev = candidates[0]
                info = _sd.query_devices(dev, "input")
                sr = int(round(info["default_samplerate"]))
                channels = min(max(1, int(info["max_input_channels"])), 2)
                hostapi_name = _sd.query_hostapis(info["hostapi"])["name"]
                extra = None
                if "WASAPI" in hostapi_name and hasattr(_sd, "WasapiSettings"):
                    extra = _sd.WasapiSettings()
                self._monitor_stream = _sd.InputStream(
                    device=dev,
                    channels=channels,
                    samplerate=sr,
                    dtype="float32",
                    blocksize=int(sr * 0.03),
                    callback=self._monitor_callback,
                    extra_settings=extra,
                )
                self._monitor_stream.start()
                self._monitoring = True
                log.info("audio monitor: running on device %d (%s)", dev, hostapi_name)
            except Exception as e:
                log.debug("audio monitor start failed: %s", e)
                self.stop_monitor()
            finally:
                if device is not None:
                    self.device = old_dev

    def stop_monitor(self) -> None:
        """Stop the non-recording audio monitor."""
        with self._monitor_lock:
            s, self._monitor_stream = self._monitor_stream, None
            self._monitoring = False
            self._monitor_level = 0.0
            if s is not None:
                try:
                    s.stop()
                except Exception:
                    pass
                try:
                    s.close()
                except Exception:
                    pass

    def current_level(self) -> float:
        """Peak absolute amplitude (~0..1) of the most recently captured audio
        block, or monitor level when previewing. For a live UI meter."""
        frames = self._frames  # snapshot: stop() rebinds _frames, so this ref stays valid
        if self._recording and frames:
            block = frames[-1]
            if block.size:
                zero_mean = block - np.mean(block)
                cur = float(np.abs(zero_mean).max())
                noise_gate = 0.015
                if cur < noise_gate:
                    return 0.0
                return float(min(1.0, (cur - noise_gate) / (0.35 - noise_gate)))
            return 0.0
        if self._monitoring:
            return float(self._monitor_level)
        return 0.0
