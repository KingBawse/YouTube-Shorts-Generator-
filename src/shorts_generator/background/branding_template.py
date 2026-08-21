"""Fit mode: a custom branding template (a PNG with a transparent "safe
area") is composited on top of the video, so a channel's logo, frame
art, or sponsor skin always appears in the same place.

The safe area rectangle (where the video shows through) is configured
in settings.ini via ``branding_safe_x/y/width/height`` and should match
the transparent hole cut into the template PNG.
"""

from __future__ import annotations

from .base import BackgroundMode, RenderPlan


class BrandingTemplateBackground(BackgroundMode):
    key = "branding_template"

    def build_plan(self) -> RenderPlan:
        w, h = self.settings.canvas_width, self.settings.canvas_height
        safe_x = self.settings.branding_safe_x
        safe_y = self.settings.branding_safe_y
        safe_w = self.settings.branding_safe_width
        safe_h = self.settings.branding_safe_height
        rate = self.video_info.fps or 30

        template_input = self._looped_image_input(self.settings.branding_template_path)

        filters = [
            # Opaque black canvas underneath everything, in case the
            # template has any additional transparent regions besides
            # the intended video safe area.
            f"color=c=black:s={w}x{h}:d={self.duration}:rate={rate}[canvas]",
            f"[0:v]scale={safe_w}:{safe_h}:force_original_aspect_ratio=decrease:flags=lanczos,setsar=1[fg]",
            f"[canvas][fg]overlay={safe_x}+({safe_w}-w)/2:{safe_y}+({safe_h}-h)/2[composited]",
            # Template goes on top last so its artwork/logo/frame always
            # wins over the video in every non-transparent pixel.
            "[composited][1:v]overlay=0:0:format=auto[outv]",
        ]
        return RenderPlan(
            extra_inputs=[template_input],
            filter_complex=";".join(filters),
            video_output_label="outv",
        )
