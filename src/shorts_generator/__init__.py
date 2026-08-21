"""
YouTube Shorts Generator
========================

A production-ready, extensible pipeline for turning ordinary landscape or
portrait source videos into vertical (9:16) "Shorts" style videos using
FFmpeg.

The package is deliberately split into small, single-purpose modules so
that the "Future Expansion" modules described in the project README
(Instagram Reels export, TikTok export, auto captions, AI subtitles,
watermarking, thumbnail generation, AI titles/descriptions/hashtags,
YouTube upload, etc.) can be added later as *plugins* without touching
the core rendering pipeline.

Package layout
---------------
    config.py            Settings.ini loading / validation
    logger.py             Logging setup + run summary log writer
    pipeline.py           Batch orchestration (skip / continue / log)
    ffmpeg/               Low level FFmpeg + FFprobe wrappers
    background/           One class per background "fit mode"
    plugins/              Extension point for future modules
    utils/                Small shared helpers
"""

__version__ = "1.0.0"
