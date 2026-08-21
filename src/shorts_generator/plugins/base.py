"""
Plugin contract for Future Expansion / Nice-to-Have modules.

How the pipeline calls plugins
-------------------------------
For every source file, in order:

1. ``before_file(context)``   -- inspect/prepare; raise to abort just this file
2. ``modify_plan(context, plan)`` -- add filters/inputs to the render plan
   (e.g. burn in a watermark, an animated subscribe button, or captions)
3. the pipeline renders the (possibly plugin-modified) plan with ffmpeg
4. ``after_render(context, output_path)`` -- act on the finished file
   (generate a thumbnail, write an AI title/description/hashtags
   sidecar file, queue a YouTube/TikTok/Instagram upload, ...)

And once per batch:

* ``before_batch(settings)``  -- e.g. open a network connection, warm a model
* ``after_batch(settings, summary)`` -- e.g. flush an upload queue, send a
  notification

A plugin only needs to override the hooks it cares about; every hook
has a harmless no-op default.

Mapping the brief's feature list onto hooks
--------------------------------------------
This mapping is here so a future implementer doesn't have to guess
which hook a given module belongs in:

* Instagram Reels export / TikTok Export
    ``after_render`` -- re-encode/re-package the finished file to each
    platform's preferred spec (aspect ratio is already correct; this is
    mostly bitrate/duration/container tweaks) and drop it in a
    platform-specific output subfolder.
* Auto Captions / AI Subtitle Generator
    ``modify_plan`` -- run speech-to-text in ``before_file`` (cache the
    transcript on the context), then add an ``ass``/``subtitles`` filter
    to the plan's filter_complex in ``modify_plan``.
* Animated Subscribe Button / Logo Watermark
    ``modify_plan`` -- add an extra image/video input plus an
    ``overlay`` filter stage on top of the mode's ``[outv]`` label (see
    ``examples.py`` for a complete worked example with a static logo).
* Thumbnail Generator / Batch Thumbnail Creator
    ``after_render`` -- run an ffmpeg ``-vframes 1`` extraction (or a
    small scoring pass to pick the "best" frame) against the finished
    output file.
* AI Titles / AI Descriptions / AI Hashtags
    IMPLEMENTED -- see ``ai_metadata.py``: an ``after_render`` hook that
    samples frames from the finished render, sends them to a
    vision-capable LLM, and writes the suggestions to a ``.json``/``.txt``
    sidecar next to the output video. Disabled by default (it costs
    money and needs your own API key) -- enable via
    ``[plugins] enabled = ai_metadata``.
* Upload to YouTube API
    ``after_batch`` -- iterate finished outputs and call the YouTube
    Data API's ``videos.insert``; batching in ``after_batch`` rather
    than per-file ``after_render`` makes it easy to add retry/backoff
    and respect API quota across the whole run.
* Automatic silence trimming / Intro-outro insertion / Fade in-out /
  Background music layer
    ``modify_plan`` -- these all compose additional filter_complex
    fragments (``silenceremove``, ``concat``, ``fade``, ``amix``)
    ahead of or after the background mode's own fragment.
* Render queue / Resume interrupted renders
    This lives at the pipeline level rather than as a plugin -- see the
    ``resume`` support already built into ``pipeline.py`` (skips files
    whose output already exists unless ``overwrite_existing`` is set).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..background.base import RenderPlan
from ..config import Settings
from ..logger import RunSummary
from ..utils.video_info import VideoInfo


@dataclass
class PluginContext:
    """Everything a plugin hook needs to know about the file currently being processed."""
    settings: Settings
    source: Path
    video_info: VideoInfo
    output_path: Path
    #: Free-form scratch space plugins can use to pass data between their
    #: own hooks for the same file (e.g. a transcript from before_file
    #: read back in modify_plan).
    scratch: dict


class RenderPlugin:
    """Base class for an optional pipeline extension.

    Subclass this, override the hooks you need, and register the class
    in ``registry.py``'s ``_REGISTRY`` (or call
    :func:`registry.register_plugin` as a decorator) so it can be turned
    on via the ``[plugins] enabled = ...`` line in settings.ini.
    """

    #: Unique key used in settings.ini's [plugins] enabled = key1,key2
    key: str = "base"

    @classmethod
    def from_settings(cls, settings: Settings) -> "RenderPlugin":
        """Construct this plugin from the global settings object.

        The default implementation takes no configuration and just
        calls the no-arg constructor. Override this when a plugin needs
        its own ``[plugin:<key>]`` section (available as
        ``settings.plugin_settings[cls.key]``, a plain ``dict`` of
        whatever keys/values that section contains) -- see
        ``ai_metadata.py`` for a worked example that reads an API key,
        model name, and a couple of numeric tuning knobs this way.
        """
        return cls()

    def before_batch(self, settings: Settings) -> None:
        """Called once before any file in the batch is processed."""

    def before_file(self, context: PluginContext) -> None:
        """Called before rendering starts for one file.

        Raise any exception to make the pipeline skip this file (the
        exception message is recorded in the run log/summary), which is
        useful for e.g. a caption plugin that can't get a transcript.
        """

    def modify_plan(self, context: PluginContext, plan: RenderPlan) -> RenderPlan:
        """Return a (possibly modified) render plan.

        The default implementation returns ``plan`` unchanged. A plugin
        that adds visual elements (watermark, subscribe button,
        captions) should append its own filter_complex fragment here,
        re-pointing ``plan.video_output_label`` at its own new output
        label, e.g.::

            new_label = "outv_watermarked"
            extra_filter = (
                f"[{plan.video_output_label}][2:v]"
                f"overlay=W-w-24:H-h-24[{new_label}]"
            )
            return RenderPlan(
                extra_inputs=plan.extra_inputs + [logo_input],
                filter_complex=plan.filter_complex + ";" + extra_filter,
                video_output_label=new_label,
            )
        """
        return plan

    def after_render(self, context: PluginContext, output_path: Path) -> None:
        """Called after a file has been rendered successfully."""

    def after_batch(self, settings: Settings, summary: RunSummary) -> None:
        """Called once after every file in the batch has been attempted."""
