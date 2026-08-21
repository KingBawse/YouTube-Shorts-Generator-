"""Fit mode: a user-supplied still image fills the canvas, in sharp focus (no blur)."""

from __future__ import annotations

from .base import BackgroundMode, RenderPlan


class SharpImageBackground(BackgroundMode):
    key = "sharp_image"

    def build_plan(self) -> RenderPlan:
        w, h = self.settings.canvas_width, self.settings.canvas_height

        image_input = self._looped_image_input(self.settings.background_image)

        filters = [
            f"[1:v]scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h}[bg]",
            self._fg_scale_filter("0:v", "fg"),
            self._overlay_centered("bg", "fg", "outv"),
        ]
        return RenderPlan(
            extra_inputs=[image_input],
            filter_complex=";".join(filters),
            video_output_label="outv",
        )
