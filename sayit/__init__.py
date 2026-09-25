import os
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_XET_HIGH_PERFORMANCE", "1")

import sys, importlib.util
from pathlib import Path

def _load_dotenv():
    """Load key-value pairs from .env into os.environ if present."""
    candidates = [
        Path(__file__).resolve().parent.parent / ".env",
        Path(sys.executable).parent / ".env",
        Path.cwd() / ".env",
    ]
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS) / ".env")

    for env_file in candidates:
        if env_file.is_file():
            try:
                with open(env_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k:
                            os.environ.setdefault(k, v)
                break
            except Exception:
                pass

_load_dotenv()

def _add_cuda_dll_dirs():
    """Put pip-installed nvidia CUDA libs on the Windows DLL search path so
    CTranslate2 can load cuBLAS/cuDNN 9 at runtime (else STT silently falls
    back to CPU). No-op off Windows / when wheels absent."""
    if sys.platform != "win32":
        return
    for pkg in ("nvidia.cublas", "nvidia.cudnn", "nvidia.cuda_nvrtc"):
        try:
            spec = importlib.util.find_spec(pkg)
        except (ModuleNotFoundError, ValueError):
            continue
        if spec and spec.submodule_search_locations:
            binp = os.path.join(spec.submodule_search_locations[0], "bin")
            if os.path.isdir(binp):
                os.add_dll_directory(binp)
                if binp not in os.environ.get("PATH", ""):
                    os.environ["PATH"] = binp + os.pathsep + os.environ.get("PATH", "")

_add_cuda_dll_dirs()

"""Say It — local dictation app core."""

__version__ = "1.0.0"
