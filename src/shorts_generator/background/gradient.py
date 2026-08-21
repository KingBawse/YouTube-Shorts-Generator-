"""Fit mode: a smooth two-color gradient fills the canvas behind the video.

We render the gradient once with Pillow into a cached PNG and then treat
it exactly like the ``sharp_image`` mode. This is more portable than
FFmpeg's ``gradients`` source filter, which is only available in
recent FFmpeg builds -- pre-rendering keeps this mode working on any
FFmpeg version that supports ``overlay`` (i.e. all of them).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image

from .base import BackgroundMode, RenderPlan

_CACHE_DIRNAME = ".shorts_generator_cache"


class GradientBackground(BackgroundMode):
    key = "gradient"

    def build_plan(self) -> RenderPlan:
        w, h = self.settings.canvas_width, self.settings.canvas_height
        image_path = self._render_gradient_png(w, h)
        image_input = self._looped_image_input(image_path)

        filters = [
            self._fg_scale_filter("0:v", "fg"),
            self._overlay_centered("1:v", "fg", "outv"),
        ]
        return RenderPlan(
            extra_inputs=[image_input],
            filter_complex=";".join(filters),
            video_output_label="outv",
        )

    def _render_gradient_png(self, w: int, h: int) -> Path:
        start = _hex_to_rgb(self.settings.gradient_color_start)
        end = _hex_to_rgb(self.settings.gradient_color_end)
        direction = self.settings.gradient_direction

        cache_dir = self.settings.output_dir.parent / _CACHE_DIRNAME
        cache_dir.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha1(f"{w}x{h}_{start}_{end}_{direction}".encode()).hexdigest()[:12]
        cache_path = cache_dir / f"gradient_{digest}.png"
        if cache_path.exists():
            return cache_path

        if direction == "vertical":
            strip = Image.new("RGB", (1, h))
            pixels = strip.load()
            for y in range(h):
                pixels[0, y] = _lerp(start, end, y / max(h - 1, 1))
            img = strip.resize((w, h), Image.LANCZOS)
        elif direction == "horizontal":
            strip = Image.new("RGB", (w, 1))
            pixels = strip.load()
            for x in range(w):
                pixels[x, 0] = _lerp(start, end, x / max(w - 1, 1))
            img = strip.resize((w, h), Image.LANCZOS)
        else:  # diagonal
            img = Image.new("RGB", (w, h))
            pixels = img.load()
            max_dist = (w - 1) + (h - 1) or 1
            for y in range(h):
                for x in range(w):
                    pixels[x, y] = _lerp(start, end, (x + y) / max_dist)

        img.save(cache_path, "PNG")
        return cache_path


def _hex_to_rgb(value: str):
    v = value.strip()
    if v.lower().startswith("0x"):
        v = v[2:]
    v = v.lstrip("#")
    if len(v) != 6:
        raise ValueError(f"Unrecognised color value: {value!r} (expected e.g. 0x1A1A2E or #1A1A2E)")
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))


def _lerp(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
