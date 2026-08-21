"""
ffprobe-backed helpers for inspecting a source video before rendering.

The pipeline uses this to fail fast (and clearly) on corrupt or
non-media files instead of letting ffmpeg produce a cryptic error deep
inside a filter_complex graph.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..exceptions import VideoProbeError


@dataclass
class VideoInfo:
    width: int
    height: int
    duration_seconds: float
    has_audio: bool
    fps: float


def probe_video(ffprobe_path: str, file_path: Path, timeout: int = 30) -> VideoInfo:
    """Run ffprobe and return basic stream information for ``file_path``.

    Raises
    ------
    VideoProbeError
        If ffprobe fails, times out, isn't found, or the file has no
        readable video stream.
    """
    command = [
        ffprobe_path,
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(file_path),
    ]
    try:
        completed = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout, text=True,
        )
    except FileNotFoundError as exc:
        raise VideoProbeError(
            f"ffprobe executable not found: '{ffprobe_path}'. "
            f"Check the [paths] ffprobe_path setting in settings.ini."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise VideoProbeError(f"ffprobe timed out inspecting {file_path.name}") from exc

    if completed.returncode != 0:
        raise VideoProbeError(
            f"ffprobe could not read {file_path.name}: {completed.stderr.strip()}"
        )

    try:
        data = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise VideoProbeError(f"ffprobe returned invalid JSON for {file_path.name}") from exc

    video_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    if video_stream is None:
        raise VideoProbeError(f"{file_path.name} has no readable video stream")

    audio_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)

    duration = _first_float(
        video_stream.get("duration"),
        data.get("format", {}).get("duration"),
    )

    fps = _parse_frame_rate(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate"))

    return VideoInfo(
        width=int(video_stream.get("width", 0)),
        height=int(video_stream.get("height", 0)),
        duration_seconds=duration or 0.0,
        has_audio=audio_stream is not None,
        fps=fps,
    )


def _first_float(*values: Optional[str]) -> Optional[float]:
    for v in values:
        if v is None:
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return None


def _parse_frame_rate(raw: Optional[str]) -> float:
    if not raw:
        return 0.0
    if "/" in raw:
        num, _, den = raw.partition("/")
        try:
            num_f, den_f = float(num), float(den)
            return num_f / den_f if den_f else 0.0
        except ValueError:
            return 0.0
    try:
        return float(raw)
    except ValueError:
        return 0.0
