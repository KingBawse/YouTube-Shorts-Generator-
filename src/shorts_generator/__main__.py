"""
Command-line entry point.

Designed for two audiences at once:

* A non-technical user who drops videos into an ``input`` folder next to
  a distributed executable and double-clicks it (or a ``.bat``/shell
  wrapper) -- running with no arguments at all reads ``settings.ini``
  from the current/executable directory and just works.
* A technical user/CI job that wants explicit control -- every setting
  can be overridden on the command line without editing settings.ini.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import ConfigError, load_settings
from .logger import setup_logging
from .pipeline import run_batch


def _default_settings_path() -> Path:
    """Locate settings.ini next to the frozen executable, or next to this script when run from source."""
    if getattr(sys, "frozen", False):
        # PyInstaller sets sys.frozen=True and sys.executable to the .exe path.
        base_dir = Path(sys.executable).resolve().parent
    else:
        base_dir = Path.cwd()
    return base_dir / "settings.ini"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="shorts-generator",
        description="Batch-convert landscape/portrait source videos into vertical YouTube Shorts.",
    )
    parser.add_argument(
        "-c", "--settings", type=Path, default=None,
        help="Path to settings.ini (default: settings.ini next to the executable/current directory).",
    )
    parser.add_argument("--input-dir", type=Path, default=None, help="Override [paths] input_dir.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Override [paths] output_dir.")
    parser.add_argument(
        "--fit-mode", type=str, default=None,
        help="Override [background] fit_mode for this run only.",
    )
    parser.add_argument(
        "--overwrite", action="store_true", default=None,
        help="Overwrite existing output files (overrides [batch] overwrite_existing).",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug-level logging.")
    parser.add_argument(
        "--print-bundled-ffmpeg", action="store_true",
        help=(
            "Diagnostic: print any auto-detected bundled ffmpeg/ffprobe paths "
            "(as FFMPEG=... / FFPROBE=... lines), actually execute '-version' "
            "on both from within this same process, and exit -- without "
            "needing settings.ini. Used by the Windows build's CI to prove "
            "FFmpeg was actually embedded in the built .exe and runs."
        ),
    )
    return parser


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)

    if args.print_bundled_ffmpeg:
        from .bundled_ffmpeg import find_bundled_binary
        import subprocess

        ffmpeg_path = find_bundled_binary("ffmpeg")
        ffprobe_path = find_bundled_binary("ffprobe")
        print(f"FFMPEG={ffmpeg_path or 'NONE'}")
        print(f"FFPROBE={ffprobe_path or 'NONE'}")

        if not ffmpeg_path or not ffprobe_path:
            print("One or both bundled binaries were not found.", file=sys.stderr)
            return 1

        # Actually execute "-version" on both binaries from *within this
        # same process*, while PyInstaller's onefile temp extraction
        # directory is still alive. That directory is deleted the moment
        # this process exits, so merely reporting the path isn't proof it
        # works -- a separate process/step trying to run it afterwards
        # would find nothing there. Running it here is the only way to
        # verify the bundled binaries genuinely execute.
        for label, path in (("ffmpeg", ffmpeg_path), ("ffprobe", ffprobe_path)):
            try:
                result = subprocess.run(
                    [path, "-version"], capture_output=True, text=True, timeout=30
                )
            except Exception as exc:  # noqa: BLE001 - report and fail, don't crash oddly
                print(f"FAILED to execute bundled {label}: {exc}", file=sys.stderr)
                return 1
            if result.returncode != 0:
                print(f"Bundled {label} exited with code {result.returncode}", file=sys.stderr)
                print(result.stderr, file=sys.stderr)
                return 1
            first_line = (result.stdout.splitlines() or [""])[0]
            print(f"{label} -version: {first_line}")

        print("Bundled ffmpeg and ffprobe both executed successfully.")
        return 0

    settings_path = args.settings or _default_settings_path()

    try:
        settings = load_settings(settings_path)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    # CLI overrides applied after loading/validating the base file.
    if args.input_dir:
        settings.input_dir = args.input_dir
    if args.output_dir:
        settings.output_dir = args.output_dir
    if args.fit_mode:
        settings.fit_mode = args.fit_mode
    if args.overwrite:
        settings.overwrite_existing = True

    logger = setup_logging(settings.log_dir, verbose=args.verbose)
    logger.info("Settings loaded from %s", settings_path)
    logger.info("Input dir  : %s", settings.input_dir)
    logger.info("Output dir : %s", settings.output_dir)
    logger.info("Fit mode   : %s", settings.fit_mode)

    summary = run_batch(settings)

    if summary.failed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
