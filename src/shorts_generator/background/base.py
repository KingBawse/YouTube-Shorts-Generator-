"""
Shared interface for all background "fit mode" implementations.

A fit mode's only job is to describe *how the canvas around the main
video is filled*. It does this by returning a :class:`RenderPlan`: any
extra FFmpeg inputs it needs (a background image, a branding template
PNG, ...) plus the ``filter_complex`` fragment that produces a final
video stream, labeled ``[outv]`` by convention, ready to be mapped to
the output file by ``ffmpeg/filters.py``.

Why this shape?
----------------
FFmpeg's ``filter_complex`` graphs compose naturally by string
concatenation (each mode appends its own semicolon-separated filter
fragment), while the *inputs* a mode needs (``-i background.jpg``,
``-loop 1 -t 8.2 -i template.png`` ...) have to be added to the command
line *before* ``-filter_complex``, in a fixed order that determines
their stream index (``0`` is always the main source video; ``1``, ``2``,
... are whatever a mode appends). Centralizing that bookkeeping here
means each concrete mode only has to think about its own filter logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List

from ..config import Settings
from ..utils.video_info import VideoInfo


@dataclass
class InputSpec:
    """Full ffmpeg argument sequence for one extra (non-main-video) input.

    Examples
    --------
    A still image looped for the duration of the clip::

        InputSpec(args=["-loop", "1", "-t", "8.2", "-i", "bg.jpg"])
    """
    args: List[str] = field(default_factory=list)


@dataclass
class RenderPlan:
    extra_inputs: List[InputSpec]
    filter_complex: str
    video_output_label: str  # label name WITHOUT surrounding brackets, e.g. "outv"


class BackgroundMode(ABC):
    """
    Base class for a background fit mode.

    Adding a brand-new fit mode later (a seasonal skin, a sponsor
    template, ...) means writing one new subclass here plus one line in
    ``factory.py`` -- nothing in the pipeline, CLI, or config loader
    needs to change, which is exactly the kind of extension point the
    project's "Future Expansion" list calls for at the application
    level (this is the same pattern the ``plugins`` package uses for
    non-rendering features).
    """

    #: Unique key referenced by settings.ini's [background] fit_mode
    key: str = "base"

    def __init__(self, settings: Settings, video_info: VideoInfo):
        self.settings = settings
        self.video_info = video_info

    @abstractmethod
    def build_plan(self) -> RenderPlan:
        """Return the extra inputs + filter_complex fragment for this mode."""
        raise NotImplementedError

    # ---- shared helpers available to every subclass ------------------

    @property
    def duration(self) -> float:
        """Source clip duration, floored to avoid a zero-length looped image."""
        return max(self.video_info.duration_seconds, 0.1)

    def _fg_scale_filter(self, label_in: str, label_out: str) -> str:
        """Scale the main video to fit the canvas width, preserving aspect ratio.

        ``force_original_aspect_ratio=decrease`` guarantees the source is
        never upscaled or cropped: it always fits entirely within the
        canvas, which is the defining property of a "fit" mode (as
        opposed to a fill/crop mode).
        """
        # flags=lanczos: a higher-quality (sharper, less blurry) resampling
        # filter than ffmpeg's default bilinear scaler -- worth the small
        # extra CPU cost since this is the scaling pass the *foreground*
        # video (the actual subject) goes through.
        w = self.settings.canvas_width
        return (
            f"[{label_in}]scale={w}:-2:force_original_aspect_ratio=decrease:flags=lanczos,"
            f"setsar=1[{label_out}]"
        )

    def _overlay_centered(self, bg_label: str, fg_label: str, out_label: str) -> str:
        return f"[{bg_label}][{fg_label}]overlay=(W-w)/2:(H-h)/2:format=auto[{out_label}]"

    def _looped_image_input(self, path) -> InputSpec:
        return InputSpec(args=["-loop", "1", "-t", str(self.duration), "-i", str(path)])
