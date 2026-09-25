"""Backward-compatibility shim forwarding wisper imports to sayit."""
import sys
import sayit

sys.modules["wisper"] = sayit
for _attr in dir(sayit):
    if not _attr.startswith("_"):
        globals()[_attr] = getattr(sayit, _attr)
