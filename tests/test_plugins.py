"""
Unit tests for the plugin architecture: settings.ini's [plugin:...]
sections being parsed into `Settings.plugin_settings`, the example
watermark plugin's filter-chain modification, and the AI metadata
plugin's config resolution / response parsing (mocked -- no real
network calls are made in these tests).
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from shorts_generator.background.base import RenderPlan
from shorts_generator.config import load_settings
from shorts_generator.plugins.ai_metadata import AIMetadataPlugin, _strip_markdown_fence
from shorts_generator.plugins.base import PluginContext
from shorts_generator.plugins.examples import ExampleWatermarkPlugin
from shorts_generator.utils.video_info import VideoInfo

SAMPLE_INI = """
[paths]
input_dir = input
output_dir = output
log_dir = logs

[plugins]
enabled = watermark, ai_metadata

[plugin:watermark]
image_path = logo.png
margin = 40

[plugin:ai_metadata]
api_key = ini-fallback-key
model = gpt-4o
frame_count = 3
"""


class PluginConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.settings_path = Path(self.tmp_dir.name) / "settings.ini"
        self.settings_path.write_text(SAMPLE_INI, encoding="utf-8")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_plugin_sections_are_parsed(self):
        settings = load_settings(self.settings_path)
        self.assertEqual(settings.enabled_plugins, ["watermark", "ai_metadata"])
        self.assertEqual(settings.plugin_settings["watermark"]["image_path"], "logo.png")
        self.assertEqual(settings.plugin_settings["watermark"]["margin"], "40")
        self.assertEqual(settings.plugin_settings["ai_metadata"]["model"], "gpt-4o")

    def test_ai_metadata_prefers_env_var_over_ini(self):
        settings = load_settings(self.settings_path)
        old = os.environ.get("OPENAI_API_KEY")
        try:
            os.environ["OPENAI_API_KEY"] = "env-key"
            plugin = AIMetadataPlugin.from_settings(settings)
            self.assertEqual(plugin.api_key, "env-key")
        finally:
            if old is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = old

    def test_ai_metadata_falls_back_to_ini_key(self):
        settings = load_settings(self.settings_path)
        old = os.environ.pop("OPENAI_API_KEY", None)
        try:
            plugin = AIMetadataPlugin.from_settings(settings)
            self.assertEqual(plugin.api_key, "ini-fallback-key")
            self.assertEqual(plugin.model, "gpt-4o")
            self.assertEqual(plugin.frame_count, 3)
        finally:
            if old is not None:
                os.environ["OPENAI_API_KEY"] = old


class MarkdownFenceTests(unittest.TestCase):
    def test_strips_json_fence(self):
        wrapped = '```json\n{"a": 1}\n```'
        self.assertEqual(_strip_markdown_fence(wrapped), '{"a": 1}')

    def test_leaves_plain_json_untouched(self):
        plain = '{"a": 1}'
        self.assertEqual(_strip_markdown_fence(plain), plain)


class WatermarkPluginTests(unittest.TestCase):
    def test_modify_plan_adds_overlay_when_image_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            logo_path = Path(tmp) / "logo.png"
            logo_path.write_bytes(b"not a real png but existence is all that's checked")

            plugin = ExampleWatermarkPlugin(image_path=logo_path, margin=24)
            base_plan = RenderPlan(extra_inputs=[], filter_complex="[0:v]copy[outv]", video_output_label="outv")
            video_info = VideoInfo(width=1920, height=1080, duration_seconds=5.0, has_audio=True, fps=30.0)
            context = PluginContext(settings=None, source=Path("in.mp4"), video_info=video_info,
                                     output_path=Path("out.mp4"), scratch={})

            new_plan = plugin.modify_plan(context, base_plan)
            self.assertEqual(len(new_plan.extra_inputs), 1)
            self.assertNotEqual(new_plan.video_output_label, "outv")
            self.assertIn("overlay=W-w-24:H-h-24", new_plan.filter_complex)

    def test_modify_plan_is_noop_when_image_missing(self):
        plugin = ExampleWatermarkPlugin(image_path=None)
        base_plan = RenderPlan(extra_inputs=[], filter_complex="[0:v]copy[outv]", video_output_label="outv")
        video_info = VideoInfo(width=1920, height=1080, duration_seconds=5.0, has_audio=True, fps=30.0)
        context = PluginContext(settings=None, source=Path("in.mp4"), video_info=video_info,
                                 output_path=Path("out.mp4"), scratch={})

        new_plan = plugin.modify_plan(context, base_plan)
        self.assertIs(new_plan, base_plan)


if __name__ == "__main__":
    unittest.main()
