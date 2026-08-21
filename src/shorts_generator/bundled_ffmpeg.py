"""
Auto-detection of an FFmpeg/FFprobe binary bundled alongside a
PyInstaller-frozen build.

Why this exists: the single biggest piece of setup friction reported
for tools like this one is FFmpeg itself -- finding the right build,
unzipping it somewhere sane, and getting it onto ``PATH`` correctly on
Windows. ``build_tools/build_exe.py`` bundles real Windows
``ffmpeg.exe`` / ``ffprobe.exe`` binaries (see ``vendor/win64/``)
directly into the built executable, and this module is what lets the
app find them automatically at runtime with zero configuration --
someone who just downloads and double-clicks the .exe never needs to
know FFmpeg is involved at all.

This is intentionally decoupled from ``config.py``'s parsing: it only
answers "is there a bundled binary?" -- ``config.py`` decides when to
prefer it over a user-specified path.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional


def find_bundled_binary(name: str) -> Optional[str]:
    """Return the path to a bundled ``name`` (e.g. "ffmpeg") binary, if any.

    Returns ``None`` when not running as a frozen (PyInstaller) build,
    or when no matching binary is found bundled -- callers should fall
    back to resolving the bare command name against ``PATH`` in that
    case, exactly as they did before bundling existed.
    """
    if not getattr(sys, "frozen", False):
        return None

    search_dirs = [Path(sys.executable).resolve().parent]
    meipass = getattr(sys, "_MEIPASS", None)  # set by PyInstaller onefile builds
    if meipass:
        search_dirs.append(Path(meipass))

    for directory in search_dirs:
        for candidate_name in (f"{name}.exe", name):
            candidate = directory / candidate_name
            if candidate.is_file():
                return str(candidate)

    return None
