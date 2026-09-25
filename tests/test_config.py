"""Self-test for Config load/save. Run: python tests/test_config.py"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sayit.config import Config


def main() -> None:
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "config.json"

        # missing file -> defaults returned AND file written
        assert not path.exists()
        cfg = Config.load(path)
        assert path.exists(), "load() must create the config file when missing"
        assert cfg == Config(), "missing file must yield defaults"

        # mutate -> save -> reload -> round-trip equal
        cfg.model = "small"
        cfg.device = "cpu"
        cfg.language = None
        cfg.save(path)
        reloaded = Config.load(path)
        assert reloaded == cfg, f"round-trip mismatch: {reloaded} != {cfg}"

        # unknown keys ignored, missing keys fall back to defaults
        path.write_text(json.dumps({"model": "tiny", "bogus_key": 123}), encoding="utf-8")
        merged = Config.load(path)
        assert merged.model == "tiny", "known key must load"
        assert not hasattr(merged, "bogus_key"), "unknown key must be ignored"
        assert merged.device == Config().device, "missing key must fall back to default"

    print("config self-test PASSED")


if __name__ == "__main__":
    main()
