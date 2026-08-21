"""
Logging setup for the Shorts Generator.

Two things are provided:

1. :func:`setup_logging` — configures the root ``shorts_generator`` logger
   to write to both the console and a timestamped log file inside the
   configured ``log_dir``. This satisfies the "Generate log" requirement
   for every batch run.

2. :class:`RunSummary` — a small accumulator the pipeline feeds
   success/skip/failure events into as it works through a batch, so a
   clean human-readable summary can be written at the end of the run
   (files processed, files skipped, total time, per-file status).
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List


def setup_logging(log_dir: Path, verbose: bool = False) -> logging.Logger:
    """Configure and return the application logger.

    Creates ``log_dir`` if necessary and attaches both a console handler
    and a file handler (one timestamped file per run, so historical runs
    are never overwritten).
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"run_{timestamp}.log"

    logger = logging.getLogger("shorts_generator")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.handlers.clear()  # avoid duplicate handlers if called twice in one process

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.debug("Log file created at %s", log_file)
    logger.info("=" * 60)
    logger.info("YouTube Shorts Generator - run started")
    logger.info("=" * 60)

    # Stash the path on the logger object so callers (e.g. the pipeline
    # summary writer) can find it without threading it through everywhere.
    logger.log_file_path = log_file  # type: ignore[attr-defined]
    return logger


@dataclass
class FileResult:
    source: Path
    status: str  # "success" | "skipped" | "failed"
    detail: str = ""
    duration_seconds: float = 0.0


@dataclass
class RunSummary:
    """Accumulates per-file outcomes for a batch run and renders a report."""

    started_at: datetime = field(default_factory=datetime.now)
    results: List[FileResult] = field(default_factory=list)

    def record(self, source: Path, status: str, detail: str = "", duration_seconds: float = 0.0) -> None:
        self.results.append(FileResult(source=source, status=status, detail=detail,
                                        duration_seconds=duration_seconds))

    @property
    def succeeded(self) -> List[FileResult]:
        return [r for r in self.results if r.status == "success"]

    @property
    def skipped(self) -> List[FileResult]:
        return [r for r in self.results if r.status == "skipped"]

    @property
    def failed(self) -> List[FileResult]:
        return [r for r in self.results if r.status == "failed"]

    def render_text(self) -> str:
        elapsed = (datetime.now() - self.started_at).total_seconds()
        lines = []
        lines.append("=" * 60)
        lines.append("BATCH SUMMARY")
        lines.append("=" * 60)
        lines.append(f"Total files considered : {len(self.results)}")
        lines.append(f"Succeeded              : {len(self.succeeded)}")
        lines.append(f"Skipped                : {len(self.skipped)}")
        lines.append(f"Failed                 : {len(self.failed)}")
        lines.append(f"Total elapsed time     : {elapsed:.1f}s")
        lines.append("-" * 60)
        for r in self.results:
            marker = {"success": "OK", "skipped": "SKIP", "failed": "FAIL"}.get(r.status, "?")
            lines.append(f"[{marker:>4}] {r.source.name} ({r.duration_seconds:.1f}s) {r.detail}")
        lines.append("=" * 60)
        return "\n".join(lines)

    def write(self, log_dir: Path) -> Path:
        """Write the summary to its own file (in addition to the run log) and return its path."""
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = self.started_at.strftime("%Y%m%d_%H%M%S")
        summary_path = log_dir / f"summary_{timestamp}.log"
        summary_path.write_text(self.render_text(), encoding="utf-8")
        return summary_path
