"""
Thin subprocess wrapper around the ``ffmpeg`` binary.

Keeping all subprocess invocation in one place makes it trivial to:

* swap in a differently-named/pathed ffmpeg binary (portable/frozen builds
  often ship their own copy next to the .exe),
* add consistent logging of the exact command line for debugging,
* centralize error handling so every caller raises the same
  :class:`~shorts_generator.exceptions.FFmpegError` on failure.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import List, Optional

from ..exceptions import FFmpegError

logger = logging.getLogger("shorts_generator.ffmpeg")


def run_ffmpeg(command: List[str], *, timeout: Optional[int] = None) -> str:
    """
    Execute an ffmpeg command.

    Parameters
    ----------
    command:
        Full command line as a list of arguments, e.g.
        ``["ffmpeg", "-y", "-i", "in.mp4", ..., "out.mp4"]``.
    timeout:
        Optional timeout in seconds; ``None`` means wait indefinitely.

    Returns
    -------
    The captured stderr text (ffmpeg logs progress/info to stderr).

    Raises
    ------
    FFmpegError
        If the process exits with a non-zero return code, times out, or
        the binary cannot be found.
    """
    logger.debug("Running command: %s", " ".join(command))
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            text=True,
        )
    except FileNotFoundError as exc:
        raise FFmpegError(
            f"ffmpeg executable not found: '{command[0]}'. "
            f"Check the [paths] ffmpeg_path setting in settings.ini.",
            command=command,
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise FFmpegError(
            f"ffmpeg timed out after {timeout}s", command=command, stderr=str(exc)
        ) from exc

    if completed.returncode != 0:
        raise FFmpegError(
            f"ffmpeg exited with status {completed.returncode}",
            command=command,
            stderr=completed.stderr,
        )

    return completed.stderr


def build_base_command(ffmpeg_path: str, overwrite: bool = True) -> List[str]:
    """Return the invariant prefix shared by every render command."""
    cmd = [ffmpeg_path]
    cmd.append("-y" if overwrite else "-n")
    # Keep ffmpeg's own console noise low; our logger captures stderr anyway
    # on failure, and progress isn't needed for unattended batch runs.
    cmd += ["-hide_banner", "-loglevel", "error"]
    return cmd
