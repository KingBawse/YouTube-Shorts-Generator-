"""Fit mode: an auto-blurred copy of the video itself fills the canvas.

This is the **default fit mode** -- it needs no background image,
branding template, or any other external asset, which is exactly what
makes it the right out-of-the-box choice for turning a landscape (16:9)
YouTube video into a vertical (9:16) Short: drop a file in `input/` and
run, nothing else to configure.

It's also the popular "blurred duplicate" look used widely on YouTube
Shorts / TikTok / Reels: the same clip is split into two branches --
one is scaled to fill and crop the full canvas, heavily blurred, and
dimmed slightly to sit behind; the other (the actual foreground
subject) is scaled to *fit* the canvas width and shown sharp on top,
never cropped and never upscaled. Only the blurred backdrop pixels are
resampled aggressively; the visible subject is a straightforward
high-quality downscale (Lanczos resampling, see `base.py`), so no
video content is lost and no artificial resolution loss is introduced
beyond what fitting a 16:9 frame into a 9:16 canvas inherently requires.
"""

from __future__ import annotations

from .base import BackgroundMode, RenderPlan


class AutoBlurVideoBackground(BackgroundMode):
    key = "auto_blur_video"

    def build_plan(self) -> RenderPlan:
        w, h = self.settings.canvas_width, self.settings.canvas_height
        sigma = self.settings.blur_sigma

        filters = [
            "[0:v]split=2[bgsrc][fgsrc]",
            f"[bgsrc]scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={w}:{h},gblur=sigma={sigma},eq=brightness=-0.05[bg]",
            self._fg_scale_filter("fgsrc", "fg"),
            self._overlay_centered("bg", "fg", "outv"),
        ]
        return RenderPlan(
            extra_inputs=[],
            filter_complex=";".join(filters),
            video_output_label="outv",
        )
