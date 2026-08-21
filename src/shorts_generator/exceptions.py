"""
Centralized exception types for the Shorts Generator.

Keeping these in one module means the batch pipeline (pipeline.py) can
catch a single, well-known exception hierarchy when deciding whether a
failure on one file should cause the whole batch to abort, or whether it
should be logged and skipped so processing of the remaining files can
continue (this is the "Skip it. Continue processing remaining files.
Generate log." behavior requested for batch runs).
"""


class ShortsGeneratorError(Exception):
    """Base class for all expected/handled errors in this application."""


class ConfigError(ShortsGeneratorError):
    """Raised when settings.ini is missing, malformed, or invalid."""


class VideoProbeError(ShortsGeneratorError):
    """Raised when ffprobe cannot read information about a source file."""


class FFmpegError(ShortsGeneratorError):
    """Raised when an ffmpeg render command exits with a non-zero status."""

    def __init__(self, message: str, command: list, stderr: str = ""):
        super().__init__(message)
        self.command = command
        self.stderr = stderr


class BackgroundModeError(ShortsGeneratorError):
    """Raised for invalid/missing configuration of a background fit mode."""


class UnsupportedFileError(ShortsGeneratorError):
    """Raised when a file in the input folder is not a supported video type."""
