"""Fit mode: a flat solid color fills the canvas behind the video.

Uses FFmpeg's ``color`` *source* filter, which needs no extra ``-i``
input at all -- it generates its own frames directly inside the
filter_complex graph, keeping the command line simple.
"""

from __future__ import annotations

from .base import BackgroundMode, RenderPlan


class SolidColorBackground(BackgroundMode):
    key = "solid_color"

    def build_plan(self) -> RenderPlan:
        w, h = self.settings.canvas_width, self.settings.canvas_height
        color = self.settings.solid_color
        rate = self.video_info.fps or 30

        filters = [
            f"color=c={color}:s={w}x{h}:d={self.duration}:rate={rate}[bg]",
            self._fg_scale_filter("0:v", "fg"),
            self._overlay_centered("bg", "fg", "outv"),
        ]
        return RenderPlan(
            extra_inputs=[],
            filter_complex=";".join(filters),
            video_output_label="outv",
        )
