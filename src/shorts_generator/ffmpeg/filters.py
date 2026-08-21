"""
Assembles a :class:`~shorts_generator.background.base.RenderPlan` into a
complete, runnable ``ffmpeg`` command line.

This is where the background mode's filter fragment, the main video
input, any extra inputs it needs, and the output encoding settings all
come together into the "Complete FFmpeg filter chain" the project asks
for. Nothing here is mode-specific -- see the ``background/`` package
for that.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from ..background.base import RenderPlan
from ..config import Settings
from .runner import build_base_command


def build_render_command(
    settings: Settings,
    source: Path,
    output: Path,
    plan: RenderPlan,
    has_audio: bool,
) -> List[str]:
    """Build the full ffmpeg argv for rendering ``source`` -> ``output``."""
    cmd = build_base_command(settings.ffmpeg_path, overwrite=settings.overwrite_existing)

    # Main source video is always input index 0.
    cmd += ["-i", str(source)]

    # Extra inputs (background image, branding template, ...) become
    # indices 1, 2, ... in the order a background mode declared them.
    for extra in plan.extra_inputs:
        cmd += extra.args

    cmd += ["-filter_complex", plan.filter_complex]
    cmd += ["-map", f"[{plan.video_output_label}]"]
    if has_audio:
        # "?" makes the map optional so a source that unexpectedly has no
        # audio stream doesn't hard-fail the whole render.
        cmd += ["-map", "0:a?"]

    cmd += ["-c:v", "libx264", "-preset", settings.preset, "-crf", str(settings.crf)]
    if settings.video_bitrate:
        cmd += ["-b:v", settings.video_bitrate]
    if settings.output_fps:
        cmd += ["-r", str(settings.output_fps)]
    cmd += ["-pix_fmt", "yuv420p"]

    if has_audio:
        cmd += ["-c:a", "aac", "-b:a", settings.audio_bitrate]
    else:
        cmd += ["-an"]

    # Places the MP4 "moov atom" at the front of the file so it starts
    # playing immediately when streamed/uploaded, instead of requiring a
    # full download first -- important for anything destined for mobile
    # upload flows (YouTube/TikTok/Instagram apps).
    cmd += ["-movflags", "+faststart"]

    cmd.append(str(output))
    return cmd
