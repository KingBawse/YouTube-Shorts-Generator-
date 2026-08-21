"""
PyInstaller build script.

Produces a single portable executable (``dist/shorts-generator`` or
``dist/shorts-generator.exe`` on Windows) that bundles Python and every
pip dependency.

On Windows, this also bundles real ``ffmpeg.exe`` / ``ffprobe.exe``
binaries directly into the executable, so the resulting
``shorts-generator.exe`` needs **nothing else installed** -- no
separate FFmpeg download, no PATH configuration. This is the single
most common source of setup friction for a tool like this one, so
removing it entirely was worth the ~150 MB it adds to the build. The
binaries themselves come from the ``ffmpeg-binaries`` PyPI package
(see ``vendor/win64/NOTICE.md`` for exactly where they're from and
their GPLv3 licensing) -- install it first with:

    pip install -r build_tools/requirements-windows.txt

IMPORTANT -- this only works when run ON Windows: PyInstaller is not a
cross-compiler. Running this script on Linux/macOS builds a
Linux/macOS executable (which will rely on a system FFmpeg install
instead). To get a real ``shorts-generator.exe``, run this script on
an actual Windows machine, or via the included GitHub Actions workflow
(``.github/workflows/build-windows.yml``), which builds it on a real
Windows runner and publishes it as a downloadable artifact/release --
see the README's "Getting a ready-made Windows .exe" section.

Usage (on Windows, to get a fully self-contained .exe)
-------------------------------------------------------
    pip install -r requirements.txt
    pip install -r build_tools/requirements-windows.txt
    python build_tools/build_exe.py

Usage (on Linux/macOS, FFmpeg NOT bundled -- uses your system FFmpeg)
-----------------------------------------------------------------------
    pip install -r requirements.txt
    python build_tools/build_exe.py

Output
------
    dist/shorts-generator(.exe)

After building, assemble a distributable folder containing:
    shorts-generator(.exe)   (FFmpeg is already inside it, on Windows)
    settings.ini              (copy from the project root, then edit)
    assets/                   (background images / branding templates you use)
    input/                    (empty folder end users drop videos into)
    output/                   (created automatically on first run)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parent.parent


def _bundled_binary_args() -> list:
    """--add-binary args pointing at real ffmpeg.exe/ffprobe.exe, Windows-only.

    PyInstaller can only bundle binaries matching the OS it's currently
    running on, so this is a no-op (with a warning) anywhere other than
    Windows. On Windows, it locates the binaries that ship inside the
    installed ``ffmpeg-binaries`` PyPI package (see
    build_tools/requirements-windows.txt) rather than requiring them to
    be checked into this repository.
    """
    if sys.platform != "win32":
        print(
            "Not running on Windows -- skipping FFmpeg bundling "
            "(the built executable will rely on a system FFmpeg install "
            "instead). Build on Windows, or via the GitHub Actions "
            "workflow, to produce a fully self-contained .exe."
        )
        return []

    try:
        import ffmpeg as ffmpeg_binaries  # provided by the `ffmpeg-binaries` package
    except ImportError:
        print(
            "WARNING: the 'ffmpeg-binaries' package is not installed, so "
            "FFmpeg cannot be bundled. Install it first:\n"
            "    pip install -r build_tools/requirements-windows.txt\n"
            "The built .exe will require a system FFmpeg install instead."
        )
        return []

    ffmpeg_path = ffmpeg_binaries.FFMPEG_PATH
    ffprobe_path = ffmpeg_binaries.FFPROBE_PATH
    if not ffmpeg_path or not ffprobe_path:
        print(
            "WARNING: 'ffmpeg-binaries' is installed but couldn't find its "
            "bundled executables. Try: python -c \"import ffmpeg; ffmpeg.init()\"\n"
            "The built .exe will require a system FFmpeg install instead."
        )
        return []

    # PyInstaller's --add-binary format is "SRC<sep>DEST", where DEST is
    # relative to the bundle root; "." places it right next to the
    # extracted app, where bundled_ffmpeg.py looks for it. The separator
    # must be the OS's own os.pathsep.
    return [
        f"--add-binary={ffmpeg_path}{os.pathsep}.",
        f"--add-binary={ffprobe_path}{os.pathsep}.",
    ]


def main() -> None:
    PyInstaller.__main__.run([
        str(ROOT / "run.py"),
        "--name=shorts-generator",
        "--onefile",
        "--console",
        f"--paths={ROOT / 'src'}",
        f"--distpath={ROOT / 'dist'}",
        f"--workpath={ROOT / 'build' / 'pyinstaller'}",
        f"--specpath={ROOT / 'build_tools'}",
        "--clean",
        "--noconfirm",
        *_bundled_binary_args(),
    ])
    print("\nBuild complete.")
    print(f"Executable: {ROOT / 'dist'}")
    print("Remember to copy settings.ini and any assets/ next to the built executable.")


if __name__ == "__main__":
    sys.exit(main())
