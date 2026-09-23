# 07 — Cross-Platform Scaling

**Scope:** How Say It runs on hardware other than the default target (Windows 11 + NVIDIA CUDA). Covers the engine-abstraction design that lets STT and LLM runtimes swap per platform, the recommended runtime per platform, rough performance tiers, and packaging.

**Not in scope:** model accuracy/benchmark comparison (see doc 02), Indic/translation (doc 03), audio capture / text injection / cleanup prompt / UI internals (they don't change per platform — that's the whole point).

**Research date:** 2026-09-22. AMD/ROCm and MLX/whisper.cpp status verified via web search where possible; unverified points are labelled.

---

## 1. The engine abstraction (lead)

Only **two** things change across platforms: the **STT backend** and the **LLM/cleanup backend**. Everything else — global hotkey, audio capture, VAD, text injection, history store, config, tray UI — is platform-generic Python and stays byte-identical. So the abstraction is deliberately small: two thin interfaces, nothing more. Do **not** abstract audio, injection, or storage behind a plugin system; they don't need it.

```python
# engines.py  — the entire abstraction surface

from typing import Protocol

class STTEngine(Protocol):
    def transcribe(self, audio: "np.ndarray", *, lang: str | None = None) -> str: ...
    # audio is 16 kHz mono float32; returns raw transcript text

class LLMEngine(Protocol):
    def clean(self, text: str, *, prompt: str) -> str: ...
    # takes raw transcript + cleanup prompt; returns cleaned text
    # may be a no-op passthrough when no local LLM is available
```

That's it. Two `Protocol`s (structural typing — no base class to inherit, no registration boilerplate). Each platform ships one concrete class per protocol. Selection is a dict keyed by a detected backend name:

```python
STT_ENGINES = {"faster-whisper": FasterWhisperSTT, "whispercpp": WhisperCppSTT, "mlx": MlxWhisperSTT}
LLM_ENGINES = {"ollama": OllamaLLM, "none": PassthroughLLM}

def pick_stt() -> STTEngine:
    name = config.get("stt_engine") or autodetect_stt()   # env override wins
    return STT_ENGINES[name]()
```

`autodetect_stt()` is a short if-ladder: CUDA present → faster-whisper; macOS/arm64 → mlx; else → whispercpp (Vulkan/CPU). Config always overrides detection so users can force a backend. **No factory classes, no DI container** — a dict and a function.

**What stays the same:** hotkey, audio, VAD, injection, history, config, UI, the cleanup *prompt itself*.
**What changes:** which `STTEngine` / `LLMEngine` concrete class is instantiated, and the wheels/binaries bundled per OS installer.

> Note: `whisper.cpp` and `mlx-whisper` both accept a decoded audio array or a file path; `faster-whisper` accepts an array. Feeding all three a 16 kHz mono float32 `np.ndarray` keeps the interface uniform. Model download/caching lives inside each concrete engine, not in the interface.

---

## 2. Per-platform recommendation table

| Platform | Recommended STT | Model size | LLM runtime | Perf tier (RTF ≈ audio-sec ÷ processing-sec; higher = faster) | Key gotchas |
|---|---|---|---|---|---|
| **NVIDIA CUDA (Windows/Linux) — baseline** | faster-whisper (CTranslate2 CUDA) | large-v3 / distil-large-v3 | Ollama (CUDA) | Very fast, RTF ~10–30× on a modern RTX; sub-second for short utterances | Needs matching CUDA runtime; cuDNN/cuBLAS DLLs must ship or be present |
| **AMD GPU — Linux** | faster-whisper via CTranslate2 **ROCm** (new, 2026) *or* whisper.cpp HIP/ROCm | medium / large-v3 | Ollama (ROCm v7) | Fast, near-CUDA on comparable silicon (unverified exact factor) | ROCm 7.x + supported card required; historically the flaky path |
| **AMD GPU — Windows** | whisper.cpp **Vulkan** (safest) *or* CTranslate2 ROCm Windows wheel (bleeding-edge) | small / medium | Ollama ROCm (RX 7000/W7000 only) *or* Vulkan | Medium–fast; Vulkan solid, ROCm-on-Windows narrow card support | Windows Radeon support is narrower than Linux; DirectML **not** a whisper.cpp backend |
| **Apple Silicon (Mac)** | mlx-whisper (MLX/Metal) *or* whisper.cpp Metal + CoreML (ANE) | large-v3 / distil / turbo | Ollama (Metal) | Fast, best perf-per-watt on Mac; ANE encoder ~3× vs CPU | First CoreML run is slow (ANE compiles model); Intel Macs are the CPU path |
| **Intel (CPU/iGPU/Arc)** | whisper.cpp **OpenVINO** (encoder on Intel CPU/iGPU/Arc) | small / medium | Ollama Vulkan (Intel) | Medium; iGPU/Arc beats plain CPU | OpenVINO accelerates the encoder only; discrete Arc newer/less-tested |
| **CPU-only fallback (any OS)** | whisper.cpp (OpenBLAS) | tiny / base / **distil-small** | Passthrough (skip LLM) or tiny Ollama model | Slow: RTF often <1× on large; usable only at tiny/base/distil | Push-to-talk short clips only; large models unusable in real time |

RTF figures are order-of-magnitude tiers, not benchmarks — see doc 02 for measured numbers.

---

## 3. Platform notes

### 3.1 NVIDIA CUDA (baseline)
faster-whisper (CTranslate2 CUDA backend) + Ollama CUDA. This is the reference implementation the rest of the app is built against. Ollama needs compute capability 5.0+ and driver 550+ (570+ for older 5.0–6.2 cards). Everything else measures against this.

### 3.2 AMD GPUs — the historical pain point, materially better in 2026
Honest status as of 2026-09-22:

- **CTranslate2 (and therefore faster-whisper) now has AMD ROCm support.** PR [#1989](https://github.com/OpenNMT/CTranslate2/pull/1989) was **merged into master on 2026-02-02**, targeting **ROCm 7.2**, shipping **Windows and Linux wheels** and Docker images. The author reports it passes all tests for whisper and gemma3, and a commenter confirmed the wheel "works out of the box on AMD Strix Halo." This closes the long-standing feature request [#1072](https://github.com/OpenNMT/CTranslate2/issues/1072). **Caveat:** it is brand new and intentionally minimal (flash attention and further optimization deferred), so treat it as bleeding-edge rather than the boring default. **Unverified (2026):** whether the ROCm wheels are on PyPI or must be built/side-loaded, and real-world stability on Windows Radeon.
- **whisper.cpp** is the safe fallback on AMD: it supports **Vulkan** (cross-vendor, driver-dependent) and **HIP/ROCm** (`-DGGML_HIP=1`). On Windows, **Vulkan is the pragmatic choice** — no ROCm install, works across Radeon generations.
- **Ollama** supports AMD ROCm on **both Linux and Windows** (ROCm/HIP v7 driver stack). **Windows Radeon support is narrower than Linux:** Windows list is RX 7000 series (7900/7800/7700/7600 XT etc.) and PRO W7000; RX 9000 and older RX 6000 cards appear on the Linux list only. Ollama also has a **Vulkan** path (default when the backend is installed) covering other vendors.
- **DirectML:** not a whisper.cpp backend (not mentioned in its README). There are separate ONNX-Runtime-DirectML Whisper paths, but they don't plug into faster-whisper or whisper.cpp, so they'd be a third engine to maintain — skip unless a Windows-AMD user has no working Vulkan/ROCm path.

**Bottom line for AMD:** Windows → whisper.cpp Vulkan is the reliable default; CTranslate2 ROCm wheels are now an option for the adventurous. Linux → ROCm works well on supported cards. This remains the platform most likely to need per-machine tweaking.

### 3.3 Apple Silicon (Mac) — often the best per-watt path
- **mlx-whisper** (`pip install mlx-whisper`) runs Whisper on Apple's MLX framework (Metal), models 39M–1.5B. Clean Python API, no C++ build. Recommended default on M-series.
- **whisper.cpp** alternative: Metal runs inference fully on GPU; **CoreML** puts the encoder on the Apple Neural Engine (>3× vs CPU per its README; first run slow while ANE compiles). An `ANEForge` path is noted as ~2× faster than the CoreML encoder for tiny–medium. **Unverified (2026):** exact mlx-whisper vs whisper.cpp-CoreML latency on current M-series — pick per doc-02 measurement.
- **Ollama** runs on Metal for the cleanup LLM.
- **Intel Macs** fall back to the CPU-only path (§3.6).

### 3.4 Intel
whisper.cpp **OpenVINO** backend (`-DWHISPER_OPENVINO=1`) runs encoder inference on Intel CPUs and integrated/discrete (Arc) GPUs. Ollama's Vulkan path covers Intel GPUs for the LLM. OpenVINO accelerates the encoder only; decoder stays on CPU, so gains are partial. Arc discrete GPUs are newer and less battle-tested — verify per machine.

### 3.5 CPU-only fallback (any OS)
whisper.cpp built with OpenBLAS. Realistic only at **tiny / base / distil-small** for interactive latency; large models run below real time (RTF < 1×) on typical CPUs and are unusable for a hotkey flow. Cleanup LLM should be **disabled (Passthrough)** or a very small Ollama model on CPU-only machines, otherwise cleanup dominates latency. This is the guaranteed-works floor, not a target experience.

### 3.6 Ryzen AI / NPUs (note only, do not build yet)
whisper.cpp lists AMD Ryzen AI NPU via VitisAI and other NPU paths (CANN/MUSA). **Speculative for Say It — skip until there's a real user on that hardware.** YAGNI.

---

## 4. Packaging / distribution (high level)

Same principle: the Python app is identical; only the bundled runtime differs.

- **Windows:** PyInstaller one-file/one-dir. CUDA build must ship or depend on cuDNN/cuBLAS DLLs (CTranslate2 needs them); the Vulkan/whisper.cpp build has no such dependency, which is another reason Vulkan is the low-friction AMD/Windows default. Prereq: recent GPU driver (CUDA-capable driver, or Vulkan-capable driver).
- **macOS:** PyInstaller or a `.app` bundle; mlx-whisper needs `ffmpeg` (Homebrew) and a recent macOS. CoreML models compile on first run. Code-signing/notarization needed for distribution.
- **Linux:** PyInstaller or a simple venv + script; ROCm builds require the ROCm 7.x stack installed system-wide (not bundleable) — document it as a prereq, don't try to ship it.
- **Later / optional:** a Tauri (preferred, lighter) or Electron shell if a richer UI is wanted; the Python core runs as a sidecar process. **Not needed for v1** — a tray app is enough. Defer.
- **Model files** are downloaded on first run per engine (HF cache / whisper.cpp GGUF / MLX), not bundled, to keep installers small.

**Ollama** is assumed installed separately by the user on every platform (it's its own installer with its own GPU detection). Say It just talks to its local HTTP API — so the LLM backend abstraction on most platforms is really "is Ollama reachable?" and the concrete class barely differs across OSes. Only STT truly varies.

---

## Assumptions & open questions for synthesis

- **Assumption:** only STT and LLM backends vary per platform; audio/injection/hotkey/history are portable Python. If any of those turn out platform-specific (e.g. Wayland vs X11 injection, macOS accessibility-permission injection), that's a *third* variance point owned by the injection doc, not here — flag to synthesis.
- **Assumption:** Ollama is a user-installed prerequisite, not bundled. If we want zero-install cleanup, we'd swap in llama.cpp bindings as an `LLMEngine` — same interface, but adds a build burden. Open question for synthesis: bundle vs require-Ollama.
- **Open (AMD):** Are CTranslate2 ROCm wheels on PyPI or side-load only? What's real Windows-Radeon stability in 2026? Needs a hands-on test before recommending faster-whisper as an AMD default over whisper.cpp Vulkan.
- **Open (Apple):** mlx-whisper vs whisper.cpp-CoreML latency on current M-series — defer to doc 02's measurements.
- **Open (perf tiers):** RTF numbers here are tiers, not measured. Synthesis should pull real figures from doc 02 to fill the table.
- **Biggest portability risk:** AMD on Windows — narrowest, newest, most-likely-to-need-tweaking runtime story despite 2026 improvements.

## Sources

- CTranslate2 AMD ROCm PR (merged 2026-02-02): https://github.com/OpenNMT/CTranslate2/pull/1989
- CTranslate2 AMD GPU feature request (closed by above): https://github.com/OpenNMT/CTranslate2/issues/1072
- whisper.cpp backends (CUDA, Vulkan, Metal, CoreML, OpenVINO, HIP/ROCm, NPU): https://github.com/ggml-org/whisper.cpp
- mlx-whisper (Apple Silicon / MLX): https://github.com/ml-explore/mlx-examples/tree/main/whisper
- Ollama GPU support (CUDA / ROCm Linux+Windows / Metal / Vulkan; Radeon card lists): https://docs.ollama.com/gpu

*Note: several performance figures are labelled unverified (2026); web search was intermittent during research, and RTF tiers should be reconciled against measured numbers in doc 02.*
