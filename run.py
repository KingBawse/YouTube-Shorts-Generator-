"""
Thin top-level launcher script.

Kept separate from ``src/shorts_generator/__main__.py`` so PyInstaller
has a single, simple entry-point file to build from (pointing
PyInstaller directly at a module inside a package that also needs to be
run with ``python -m`` during development is needlessly fiddly).

Usage from source:
    python run.py --help

This is also the file `build_tools/build_exe.py` hands to PyInstaller.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from shorts_generator.__main__ import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
