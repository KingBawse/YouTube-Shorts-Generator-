"""
Batch orchestration.

This is the top-level loop: scan the input folder, and for every source
file, probe it, build a background render plan, let any enabled plugins
adjust that plan, render it with ffmpeg, and record the outcome.

Failure handling follows one rule throughout: a problem with ONE file
must never stop the batch. Every per-file step is wrapped so that any
expected error --

    * a corrupt/unreadable source file (VideoProbeError)
    * a bad background-mode configuration (BackgroundModeError)
    * an ffmpeg render failure (FFmpegError)
    * a plugin raising out of ``before_file``

-- results in that one file being logged and skipped, with processing
continuing on to the next file. A full, timestamped run log plus a
human-readable batch summary are always written at the end, regardless
of how many files failed (the "Skip it. Continue processing remaining
files. Generate log." requirement).
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from .background.factory import get_background_mode
from .config import Settings
from .exceptions import ShortsGeneratorError
from .ffmpeg.filters import build_render_command
from .ffmpeg.runner import run_ffmpeg
from .logger import RunSummary
from .plugins.base import PluginContext
from .plugins.registry import get_enabled_plugins
from .utils.validators import discover_input_files
from .utils.video_info import probe_video

logger = logging.getLogger("shorts_generator.pipeline")


def _output_path_for(settings: Settings, source: Path) -> Path:
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    name = f"{source.stem}{settings.output_suffix}.{settings.container_extension}"
    return settings.output_dir / name


def process_one_file(settings: Settings, source: Path, plugins) -> Path:
    """Render a single source file. Raises on any failure; never catches."""
    output_path = _output_path_for(settings, source)

    if output_path.exists() and not settings.overwrite_existing:
        raise FileExistsError(
            f"Output already exists (set overwrite_existing=true to re-render): {output_path.name}"
        )

    video_info = probe_video(settings.ffprobe_path, source)

    mode = get_background_mode(settings, video_info)
    plan = mode.build_plan()

    context = PluginContext(
        settings=settings, source=source, video_info=video_info,
        output_path=output_path, scratch={},
    )
    for plugin in plugins:
        plugin.before_file(context)
    for plugin in plugins:
        plan = plugin.modify_plan(context, plan)

    command = build_render_command(settings, source, output_path, plan, has_audio=video_info.has_audio)
    run_ffmpeg(command)

    for plugin in plugins:
        plugin.after_render(context, output_path)

    return output_path


def run_batch(settings: Settings) -> RunSummary:
    """Process every supported video file in ``settings.input_dir``.

    Returns a :class:`RunSummary`; also writes it to ``settings.log_dir``.
    Never raises for individual file failures -- only for conditions that
    make the whole batch meaningless (e.g. the input directory not
    existing at all is still reported gracefully, just with zero files).
    """
    summary = RunSummary()
    plugins = get_enabled_plugins(settings)

    files = discover_input_files(settings.input_dir)
    if not files:
        logger.warning("No supported video files found in %s", settings.input_dir)
    else:
        logger.info("Found %d file(s) to process in %s", len(files), settings.input_dir)

    for plugin in plugins:
        try:
            plugin.before_batch(settings)
        except Exception as exc:  # noqa: BLE001 - a plugin failing to start must not kill the batch
            logger.error("Plugin '%s' failed during before_batch: %s", plugin.key, exc)

    for source in files:
        started = time.monotonic()
        logger.info("Processing: %s", source.name)
        try:
            output_path = process_one_file(settings, source, plugins)
        except FileExistsError as exc:
            elapsed = time.monotonic() - started
            logger.info("Skipping %s: %s", source.name, exc)
            summary.record(source, "skipped", detail=str(exc), duration_seconds=elapsed)
            continue
        except ShortsGeneratorError as exc:
            # Expected, "known" failure modes: log clearly, skip, and
            # continue with the next file in the batch.
            elapsed = time.monotonic() - started
            logger.error("Skipping %s due to error: %s", source.name, exc)
            summary.record(source, "failed", detail=str(exc), duration_seconds=elapsed)
            continue
        except Exception as exc:  # noqa: BLE001 - last-resort safety net for one bad file
            elapsed = time.monotonic() - started
            logger.exception("Unexpected error processing %s -- skipping it.", source.name)
            summary.record(source, "failed", detail=f"Unexpected error: {exc}", duration_seconds=elapsed)
            continue

        elapsed = time.monotonic() - started
        logger.info("Done: %s -> %s (%.1fs)", source.name, output_path.name, elapsed)
        summary.record(source, "success", detail=str(output_path), duration_seconds=elapsed)

        if settings.delete_source_on_success:
            try:
                source.unlink()
                logger.debug("Deleted source after successful render: %s", source)
            except OSError as exc:
                logger.warning("Could not delete source %s: %s", source, exc)

    for plugin in plugins:
        try:
            plugin.after_batch(settings, summary)
        except Exception as exc:  # noqa: BLE001
            logger.error("Plugin '%s' failed during after_batch: %s", plugin.key, exc)

    logger.info("\n%s", summary.render_text())
    summary_path = summary.write(settings.log_dir)
    logger.info("Summary written to %s", summary_path)

    return summary
