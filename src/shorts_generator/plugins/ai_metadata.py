"""
AI-generated title / description / hashtag suggestions for every
rendered Short, aimed at maximizing algorithmic reach.

How it works
------------
For each successfully rendered file, this plugin:

1. Samples a handful of evenly-spaced frames from the finished vertical
   video with ffmpeg.
2. Sends those frames (as base64 JPEGs) plus the original filename to
   OpenAI's Chat Completions API using a vision-capable model
   (``gpt-4o-mini`` by default), with a system prompt that encodes
   well-established short-form video growth practices.
3. Parses the model's JSON reply and writes it next to the rendered
   video as both a machine-readable ``.metadata.json`` and a
   human-readable ``.metadata.txt`` sidecar file.

This calls out to a paid third-party API using your own credentials --
it is NOT enabled by default. It also fails open: any problem (no API
key configured, network error, malformed response, ...) is logged as a
warning and simply skips metadata generation for that one file. It
never marks an otherwise-successful render as failed, and it never
stops the batch.

Setup
-----
    [plugins]
    enabled = ai_metadata

    [plugin:ai_metadata]
    ; Prefer the OPENAI_API_KEY environment variable over storing a key
    ; in this file -- api_key here is only a fallback for convenience.
    api_key =
    model = gpt-4o-mini
    frame_count = 5
    max_output_tokens = 900

Privacy note: enabling this plugin sends sampled video frames from
every rendered Short to OpenAI's API for analysis.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import List, Optional

from ..config import Settings
from .base import PluginContext, RenderPlugin
from .registry import register_plugin

logger = logging.getLogger("shorts_generator.plugins.ai_metadata")

_API_URL = "https://api.openai.com/v1/chat/completions"

_SYSTEM_PROMPT = """You are a YouTube Shorts / short-form video growth strategist.
You are shown several sampled frames from one short vertical video plus its
original filename. Your job is to propose metadata that maximizes algorithmic
distribution and click-through, using legitimate, non-misleading growth tactics
(no clickbait that misrepresents the content, no banned/spam terms, no excessive
punctuation or ALL CAPS).

Follow these principles:
- Titles: front-load a concrete hook or curiosity gap in the first 3-5 words,
  include a searchable keyword relevant to the visible content, stay under 100
  characters (YouTube's title limit), and never promise something the footage
  doesn't deliver.
- Description: 1-3 sentences that reinforce the hook and add searchable
  keywords naturally, end with a short call-to-action (e.g. "Follow for
  more"), then include the hashtag list.
- Hashtags: 3-8 tags, mixing one broad/high-volume tag (e.g. #shorts), 1-2
  mid-volume niche tags relevant to the content category, and 1-2
  specific/long-tail tags describing exactly what's shown. No spaces inside a
  hashtag.
- Tags: 8-15 flat (non-#) keyword phrases for YouTube's classic "tags" field,
  ordered most-important first.

Respond with ONLY a single JSON object, no prose, no markdown fences, matching
exactly this shape:
{"titles": ["...", "...", "...", "...", "..."], "description": "...",
"hashtags": ["#...", "#..."], "tags": ["...", "..."]}
"""


@register_plugin
class AIMetadataPlugin(RenderPlugin):
    key = "ai_metadata"

    def __init__(self, api_key: Optional[str], model: str, frame_count: int,
                 max_output_tokens: int, ffmpeg_path: str):
        self.api_key = api_key
        self.model = model
        self.frame_count = max(1, frame_count)
        self.max_output_tokens = max_output_tokens
        self.ffmpeg_path = ffmpeg_path

    @classmethod
    def from_settings(cls, settings: Settings) -> "AIMetadataPlugin":
        section = settings.plugin_settings.get("ai_metadata", {})
        # Environment variable takes priority: it keeps the key out of a
        # settings.ini file that might get copied, zipped, or committed.
        api_key = os.environ.get("OPENAI_API_KEY") or section.get("api_key", "").strip() or None
        return cls(
            api_key=api_key,
            model=section.get("model", "gpt-4o-mini").strip() or "gpt-4o-mini",
            frame_count=int(section.get("frame_count", 5)),
            max_output_tokens=int(section.get("max_output_tokens", 900)),
            ffmpeg_path=settings.ffmpeg_path,
        )

    def before_batch(self, settings: Settings) -> None:
        if not self.api_key:
            logger.warning(
                "ai_metadata plugin is enabled but no OpenAI API key was found. "
                "Set the OPENAI_API_KEY environment variable, or 'api_key' under "
                "[plugin:ai_metadata] in settings.ini. Title/hashtag suggestions "
                "will be skipped for this run."
            )

    def after_render(self, context: PluginContext, output_path: Path) -> None:
        if not self.api_key:
            return

        frames: List[str] = []
        tmp_dir: Optional[Path] = None
        try:
            tmp_dir, frames = self._extract_frames(output_path, context.video_info.duration_seconds)
            if not frames:
                logger.warning("Could not sample frames from %s; skipping AI suggestions.", output_path.name)
                return

            suggestions = self._request_suggestions(frames, context.source.name)
            self._write_sidecar(output_path, suggestions)
            logger.info("AI title/hashtag suggestions written for %s", output_path.name)
        except Exception as exc:  # noqa: BLE001 - a metadata failure must never fail the render
            logger.warning("AI metadata generation failed for %s: %s", output_path.name, exc)
        finally:
            if tmp_dir is not None:
                shutil.rmtree(tmp_dir, ignore_errors=True)

    # ---- internals -----------------------------------------------------

    def _extract_frames(self, video_path: Path, duration: float):
        duration = max(duration, 0.5)
        tmp_dir = Path(tempfile.mkdtemp(prefix="shorts_ai_frames_"))
        paths = []
        for i in range(self.frame_count):
            # Evenly spaced strictly between 0 and duration, avoiding the
            # very first/last frames which are often black or mid-transition.
            t = duration * (i + 1) / (self.frame_count + 1)
            out_path = tmp_dir / f"frame_{i}.jpg"
            command = [
                self.ffmpeg_path, "-y", "-hide_banner", "-loglevel", "error",
                "-ss", f"{t:.2f}", "-i", str(video_path),
                "-frames:v", "1", "-q:v", "3", str(out_path),
            ]
            try:
                subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=30, check=True)
                if out_path.exists():
                    paths.append(str(out_path))
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                logger.debug("Frame extraction failed at t=%.2fs for %s: %s", t, video_path.name, exc)
        return tmp_dir, paths

    def _request_suggestions(self, frame_paths: List[str], source_filename: str) -> dict:
        content = [{"type": "text", "text": f"Original source filename: {source_filename}"}]
        for path in frame_paths:
            b64 = base64.b64encode(Path(path).read_bytes()).decode("ascii")
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            })

        payload = {
            "model": self.model,
            "max_tokens": self.max_output_tokens,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
        }
        request = urllib.request.Request(
            _API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI API error {exc.code}: {error_body[:300]}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Could not reach OpenAI API: {exc}") from exc

        raw_text = body["choices"][0]["message"]["content"].strip()
        raw_text = _strip_markdown_fence(raw_text)
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Could not parse model response as JSON: {raw_text[:300]}") from exc
        return parsed

    def _write_sidecar(self, output_path: Path, suggestions: dict) -> None:
        json_path = output_path.with_name(output_path.name + ".metadata.json")
        json_path.write_text(json.dumps(suggestions, indent=2), encoding="utf-8")

        lines = ["TITLE SUGGESTIONS", "-" * 40]
        for i, title in enumerate(suggestions.get("titles", []), start=1):
            lines.append(f"{i}. {title}")
        lines += ["", "DESCRIPTION", "-" * 40, suggestions.get("description", "")]
        lines += ["", "HASHTAGS", "-" * 40, " ".join(suggestions.get("hashtags", []))]
        lines += ["", "TAGS", "-" * 40, ", ".join(suggestions.get("tags", []))]

        txt_path = output_path.with_name(output_path.name + ".metadata.txt")
        txt_path.write_text("\n".join(lines), encoding="utf-8")


def _strip_markdown_fence(text: str) -> str:
    """Some models wrap JSON in ```json ... ``` even when told not to; tolerate it."""
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    return text.strip()
