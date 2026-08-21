"""Fit mode: the canvas is split into a top and bottom band, each a
blurred, mirrored crop of the source video, with the sharp video
centered across the seam. A symmetric, "poster-style" background that
needs no external assets.
"""

from __future__ import annotations

from .base import BackgroundMode, RenderPlan


class SplitTopBottomBackground(BackgroundMode):
    key = "split_top_bottom"

    def build_plan(self) -> RenderPlan:
        w, h = self.settings.canvas_width, self.settings.canvas_height
        band_h = h // 2
        remainder = h - band_h * 2  # absorbed into the bottom band if h is odd
        sigma = self.settings.blur_sigma

        filters = [
            "[0:v]split=3[topsrc][bottomsrc][fgsrc]",
            f"[topsrc]scale={w}:{band_h}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={w}:{band_h},gblur=sigma={sigma}[bandtop]",
            f"[bottomsrc]scale={w}:{band_h + remainder}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={w}:{band_h + remainder},gblur=sigma={sigma},hflip,vflip[bandbottom]",
            "[bandtop][bandbottom]vstack=inputs=2[bg]",
            self._fg_scale_filter("fgsrc", "fg"),
            self._overlay_centered("bg", "fg", "outv"),
        ]
        return RenderPlan(
            extra_inputs=[],
            filter_complex=";".join(filters),
            video_output_label="outv",
        )
