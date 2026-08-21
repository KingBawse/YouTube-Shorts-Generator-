"""Fit mode: a user-supplied still image, blurred, fills the canvas behind the video.

This is the "current floral style" mentioned in the project brief: a
pretty but out-of-focus static image sits behind the sharp foreground
video so the eye is drawn to the subject while the background still
feels intentional rather than empty letterboxing.
"""

from __future__ import annotations

from .base import BackgroundMode, RenderPlan


class BlurredImageBackground(BackgroundMode):
    key = "blurred_image"

    def build_plan(self) -> RenderPlan:
        w, h = self.settings.canvas_width, self.settings.canvas_height
        sigma = self.settings.blur_sigma

        image_input = self._looped_image_input(self.settings.background_image)

        filters = [
            # Fill the whole canvas with the image (cropping any excess)
            # then blur it heavily so it reads as texture, not detail.
            f"[1:v]scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={w}:{h},gblur=sigma={sigma}[bg]",
            self._fg_scale_filter("0:v", "fg"),
            self._overlay_centered("bg", "fg", "outv"),
        ]
        return RenderPlan(
            extra_inputs=[image_input],
            filter_complex=";".join(filters),
            video_output_label="outv",
        )
