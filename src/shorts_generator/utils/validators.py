"""Filesystem/input validation helpers shared across the pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import List

from ..config import SUPPORTED_INPUT_EXTENSIONS


def discover_input_files(input_dir: Path) -> List[Path]:
    """Return all supported video files directly inside ``input_dir``, sorted by name.

    Non-recursive by design: batch jobs are simplest to reason about (and
    to re-run safely) when the input folder is a flat drop zone. Sorting
    gives deterministic, reproducible run logs.
    """
    if not input_dir.exists():
        return []
    return sorted(
        p for p in input_dir.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_INPUT_EXTENSIONS
    )
