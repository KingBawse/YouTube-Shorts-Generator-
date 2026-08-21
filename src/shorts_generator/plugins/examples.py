"""
Reference plugin implementation.

This module is intentionally the ONLY plugin shipped with the core
application, and it is NOT enabled by default. Its sole purpose is to
be a working, tested example that future modules (logo watermark,
animated subscribe button, thumbnail generator, AI titles, YouTube
upload, ...) can copy the shape of -- see ``base.py``'s module
docstring for how each item on the brief's feature list maps onto the
hooks demonstrated here.

ExampleWatermarkPlugin
----------------------
Burns a static logo image into the bottom-right corner of the finished
frame, on top of whatever the background mode already produced. This
is deliberately the simplest possible ``modify_plan`` implementation:
one extra input, one extra ``overlay`` filter stage.

To try it: set ``image_path`` under a ``[plugin:watermark]`` section in
settings.ini and add ``watermark`` to ``[plugins] enabled = watermark``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from ..background.base import InputSpec, RenderPlan
from ..config import Settings
from .base import PluginContext, RenderPlugin
from .registry import register_plugin

logger = logging.getLogger("shorts_generator.plugins.watermark")


@register_plugin
class ExampleWatermarkPlugin(RenderPlugin):
    key = "watermark"

    def __init__(self, image_path: Optional[Path] = None, margin: int = 24):
        self.image_path = image_path
        self.margin = margin

    @classmethod
    def from_settings(cls, settings: Settings) -> "ExampleWatermarkPlugin":
        section = settings.plugin_settings.get("watermark", {})
        raw_path = section.get("image_path", "").strip()
        return cls(
            image_path=Path(raw_path) if raw_path else None,
            margin=int(section.get("margin", 24)),
        )

    def before_batch(self, settings: Settings) -> None:
        if not self.image_path:
            logger.warning(
                "watermark plugin is enabled but no 'image_path' is set under "
                "[plugin:watermark] in settings.ini -- no watermark will be applied."
            )
        elif not self.image_path.exists():
            logger.warning("watermark plugin: image_path not found: %s", self.image_path)

    def modify_plan(self, context: PluginContext, plan: RenderPlan) -> RenderPlan:
        if not self.image_path or not Path(self.image_path).exists():
            # Fail open: a misconfigured optional plugin should never
            # break the core render.
            return plan

        logo_index = len(plan.extra_inputs) + 1  # +1 because index 0 is the main video
        logo_input = InputSpec(args=["-i", str(self.image_path)])
        new_label = "outv_watermarked"
        extra_filter = (
            f"[{plan.video_output_label}][{logo_index}:v]"
            f"overlay=W-w-{self.margin}:H-h-{self.margin}[{new_label}]"
        )
        return RenderPlan(
            extra_inputs=[*plan.extra_inputs, logo_input],
            filter_complex=plan.filter_complex + ";" + extra_filter,
            video_output_label=new_label,
        )
