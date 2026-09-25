"""Say It Desktop Application entrypoint for development and PyInstaller packaging."""
import sys
import os
from pathlib import Path

project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from sayit.__main__ import main

if __name__ == "__main__":
    main()
