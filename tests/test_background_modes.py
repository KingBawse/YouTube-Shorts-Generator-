"""
Unit tests for the background fit-mode filter-chain builders.

These tests deliberately do NOT invoke ffmpeg itself (that's covered by
the manual smoke test in the README / CI integration test) -- they only
assert that each mode produces a well-formed RenderPlan: the expected
number of extra inputs, and a filter_complex string that references
every label it declares.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from shorts_generator.background.factory import get_background_mode
from shorts_generator.config import Settings
from shorts_generator.utils.video_info import VideoInfo

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def make_settings(**overrides) -> Settings:
    defaults = dict(
        input_dir=Path("input"),
        output_dir=Path("output"),
        log_dir=Path("logs"),
        ffmpeg_path="ffmpeg",
        ffprobe_path="ffprobe",
        canvas_width=1080,
        canvas_height=1920,
        output_fps=None,
        video_bitrate="",
        audio_bitrate="192k",
        crf=20,
        preset="veryfast",
        container_extension="mp4",
        fit_mode="blurred_image",
        background_image=FIXTURES / "bg.jpg",
        blur_sigma=20,
        solid_color="0x1A1A2E",
        gradient_color_start="0x1A1A2E",
        gradient_color_end="0x16213E",
        gradient_direction="vertical",
        branding_template_path=FIXTURES / "template.png",
        branding_safe_x=0,
        branding_safe_y=156,
        branding_safe_width=1080,
        branding_safe_height=1608,
        overwrite_existing=False,
        continue_on_error=True,
        delete_source_on_success=False,
        enabled_plugins=[],
    )
    defaults.update(overrides)
    return Settings(**defaults)


def make_video_info(**overrides) -> VideoInfo:
    defaults = dict(width=1920, height=1080, duration_seconds=12.4, has_audio=True, fps=30.0)
    defaults.update(overrides)
    return VideoInfo(**defaults)


class BackgroundModeTests(unittest.TestCase):
    def _assert_valid_plan(self, plan, expected_extra_inputs: int):
        self.assertEqual(len(plan.extra_inputs), expected_extra_inputs)
        self.assertIn(f"[{plan.video_output_label}]", plan.filter_complex)
        # Every extra input must be at least "-i <something>"
        for spec in plan.extra_inputs:
            self.assertIn("-i", spec.args)

    def test_blurred_image(self):
        settings = make_settings(fit_mode="blurred_image")
        plan = get_background_mode(settings, make_video_info()).build_plan()
        self._assert_valid_plan(plan, expected_extra_inputs=1)
        self.assertIn("gblur", plan.filter_complex)

    def test_sharp_image(self):
        settings = make_settings(fit_mode="sharp_image")
        plan = get_background_mode(settings, make_video_info()).build_plan()
        self._assert_valid_plan(plan, expected_extra_inputs=1)
        self.assertNotIn("gblur", plan.filter_complex)

    def test_solid_color(self):
        settings = make_settings(fit_mode="solid_color")
        plan = get_background_mode(settings, make_video_info()).build_plan()
        self._assert_valid_plan(plan, expected_extra_inputs=0)
        self.assertIn("color=c=0x1A1A2E", plan.filter_complex)

    def test_gradient(self):
        settings = make_settings(fit_mode="gradient")
        plan = get_background_mode(settings, make_video_info()).build_plan()
        self._assert_valid_plan(plan, expected_extra_inputs=1)

    def test_auto_blur_video(self):
        settings = make_settings(fit_mode="auto_blur_video")
        plan = get_background_mode(settings, make_video_info()).build_plan()
        self._assert_valid_plan(plan, expected_extra_inputs=0)
        self.assertIn("split=2", plan.filter_complex)

    def test_split_top_bottom(self):
        settings = make_settings(fit_mode="split_top_bottom")
        plan = get_background_mode(settings, make_video_info()).build_plan()
        self._assert_valid_plan(plan, expected_extra_inputs=0)
        self.assertIn("vstack", plan.filter_complex)

    def test_branding_template(self):
        settings = make_settings(fit_mode="branding_template")
        plan = get_background_mode(settings, make_video_info()).build_plan()
        self._assert_valid_plan(plan, expected_extra_inputs=1)
        self.assertIn("overlay=0:0", plan.filter_complex)


if __name__ == "__main__":
    unittest.main()
