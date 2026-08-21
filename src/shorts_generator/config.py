"""
Configuration loading for the Shorts Generator.

All user-tunable behaviour lives in a single ``settings.ini`` file so the
compiled/frozen (PyInstaller) executable can be reconfigured by end users
without touching Python source. See ``settings.ini`` in the project root
for a fully-commented sample.

Design notes
------------
* We use the standard-library ``configparser`` rather than a third-party
  dependency to keep the PyInstaller build small and dependency-light.
* ``Settings`` is a plain dataclass so the rest of the codebase gets
  attribute access + type hints instead of dict-key lookups (``cfg["x"]``
  typos fail loudly at development time instead of silently at runtime).
* Validation happens once, eagerly, in :func:`load_settings`, so every
  other module can assume the settings object it receives is well formed.
"""

from __future__ import annotations

import configparser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .bundled_ffmpeg import find_bundled_binary
from .exceptions import ConfigError

# Background fit modes supported by the core application. Kept as a
# constant here (rather than inferred from the background/ package) so
# config validation can give a clear error message before the pipeline
# even starts importing renderer classes.
SUPPORTED_FIT_MODES = (
    "blurred_image",
    "sharp_image",
    "solid_color",
    "gradient",
    "auto_blur_video",
    "split_top_bottom",
    "branding_template",
)

SUPPORTED_INPUT_EXTENSIONS = (".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm")


@dataclass
class Settings:
    # --- Paths -----------------------------------------------------
    input_dir: Path
    output_dir: Path
    log_dir: Path
    ffmpeg_path: str
    ffprobe_path: str

    # --- Canvas / output -----------------------------------------------
    canvas_width: int
    canvas_height: int
    output_fps: Optional[int]
    video_bitrate: str
    audio_bitrate: str
    crf: int
    preset: str
    container_extension: str

    # --- Background fit mode ----------------------------------------
    fit_mode: str
    background_image: Optional[Path]
    blur_sigma: int
    solid_color: str
    gradient_color_start: str
    gradient_color_end: str
    gradient_direction: str
    branding_template_path: Optional[Path]
    branding_safe_x: int
    branding_safe_y: int
    branding_safe_width: int
    branding_safe_height: int

    # --- Batch behaviour ----------------------------------------------
    overwrite_existing: bool
    continue_on_error: bool
    delete_source_on_success: bool

    # --- Plugin toggles (future expansion placeholders) ----------------
    enabled_plugins: list = field(default_factory=list)
    #: Raw key/value pairs from any [plugin:<key>] section, keyed by
    #: plugin key. Lets a plugin read its own configuration (API keys,
    #: model names, ...) without settings.ini/Settings needing to know
    #: about every plugin that might ever exist.
    plugin_settings: dict = field(default_factory=dict)

    # --- Misc -----------------------------------------------------------
    output_suffix: str = "_short"


def _get_path(parser: configparser.ConfigParser, section: str, key: str,
              default: str, base_dir: Path) -> Path:
    raw = parser.get(section, key, fallback=default).strip()
    p = Path(raw)
    if not p.is_absolute():
        p = (base_dir / p).resolve()
    return p


def _get_optional_path(parser: configparser.ConfigParser, section: str, key: str,
                        base_dir: Path) -> Optional[Path]:
    raw = parser.get(section, key, fallback="").strip()
    if not raw:
        return None
    p = Path(raw)
    if not p.is_absolute():
        p = (base_dir / p).resolve()
    return p


def load_settings(settings_path: Path, base_dir: Optional[Path] = None) -> Settings:
    """
    Load and validate ``settings.ini``.

    Parameters
    ----------
    settings_path:
        Path to the settings.ini file.
    base_dir:
        Directory that relative paths inside settings.ini are resolved
        against. Defaults to the folder containing settings.ini, which is
        the intuitive behaviour for a double-clicked/frozen executable
        distributed alongside its settings file.

    Raises
    ------
    ConfigError
        If the file is missing, malformed, or contains invalid values.
    """
    settings_path = Path(settings_path)
    if not settings_path.exists():
        raise ConfigError(f"Settings file not found: {settings_path}")

    base_dir = base_dir or settings_path.parent

    parser = configparser.ConfigParser()
    try:
        parser.read(settings_path, encoding="utf-8")
    except configparser.Error as exc:
        raise ConfigError(f"Could not parse {settings_path}: {exc}") from exc

    try:
        # Calling getint/getboolean/get directly on the parser (rather than
        # indexing parser["section"] first) means a missing section falls
        # back cleanly to the provided default instead of raising
        # NoSectionError -- every setting in this file is optional and a
        # minimal settings.ini overriding just one or two values is
        # expected to work.
        fit_mode = parser.get("background", "fit_mode", fallback="auto_blur_video").strip().lower()
        if fit_mode not in SUPPORTED_FIT_MODES:
            raise ConfigError(
                f"Invalid [background] fit_mode='{fit_mode}'. "
                f"Must be one of: {', '.join(SUPPORTED_FIT_MODES)}"
            )

        ffmpeg_path = parser.get("paths", "ffmpeg_path", fallback="ffmpeg").strip() or "ffmpeg"
        ffprobe_path = parser.get("paths", "ffprobe_path", fallback="ffprobe").strip() or "ffprobe"
        # Only auto-substitute a bundled binary when the setting is still at
        # its bare default ("ffmpeg"/"ffprobe", meaning "resolve against
        # PATH") -- an explicit custom path in settings.ini is always
        # respected as-is. In a build produced by build_tools/build_exe.py,
        # this is what lets a downloaded .exe work immediately with no
        # FFmpeg installed on the machine at all.
        if ffmpeg_path == "ffmpeg":
            ffmpeg_path = find_bundled_binary("ffmpeg") or ffmpeg_path
        if ffprobe_path == "ffprobe":
            ffprobe_path = find_bundled_binary("ffprobe") or ffprobe_path

        settings = Settings(
            input_dir=_get_path(parser, "paths", "input_dir", "input", base_dir),
            output_dir=_get_path(parser, "paths", "output_dir", "output", base_dir),
            log_dir=_get_path(parser, "paths", "log_dir", "logs", base_dir),
            ffmpeg_path=ffmpeg_path,
            ffprobe_path=ffprobe_path,

            canvas_width=parser.getint("output", "canvas_width", fallback=1080),
            canvas_height=parser.getint("output", "canvas_height", fallback=1920),
            output_fps=(parser.getint("output", "output_fps", fallback=0) or None),
            video_bitrate=parser.get("output", "video_bitrate", fallback="").strip(),
            audio_bitrate=parser.get("output", "audio_bitrate", fallback="192k").strip(),
            # Defaults favor quality over render speed: crf=18 is close to
            # visually lossless, and preset=slow buys noticeably better
            # quality-per-bit than a fast preset at the cost of longer
            # render times. Both are user-tunable per the comments in
            # settings.ini if faster turnaround matters more to you.
            crf=parser.getint("output", "crf", fallback=18),
            preset=parser.get("output", "preset", fallback="slow").strip(),
            container_extension=parser.get("output", "container_extension", fallback="mp4").strip().lstrip("."),
            output_suffix=parser.get("output", "output_suffix", fallback="_short").strip(),

            fit_mode=fit_mode,
            background_image=_get_optional_path(parser, "background", "background_image", base_dir),
            blur_sigma=parser.getint("background", "blur_sigma", fallback=20),
            solid_color=parser.get("background", "solid_color", fallback="0x1A1A2E").strip(),
            gradient_color_start=parser.get("background", "gradient_color_start", fallback="0x1A1A2E").strip(),
            gradient_color_end=parser.get("background", "gradient_color_end", fallback="0x16213E").strip(),
            gradient_direction=parser.get("background", "gradient_direction", fallback="vertical").strip().lower(),
            branding_template_path=_get_optional_path(parser, "background", "branding_template_path", base_dir),
            branding_safe_x=parser.getint("background", "branding_safe_x", fallback=0),
            branding_safe_y=parser.getint("background", "branding_safe_y", fallback=156),
            branding_safe_width=parser.getint("background", "branding_safe_width", fallback=1080),
            branding_safe_height=parser.getint("background", "branding_safe_height", fallback=1608),

            overwrite_existing=parser.getboolean("batch", "overwrite_existing", fallback=False),
            continue_on_error=parser.getboolean("batch", "continue_on_error", fallback=True),
            delete_source_on_success=parser.getboolean("batch", "delete_source_on_success", fallback=False),

            enabled_plugins=[
                name.strip() for name in parser.get("plugins", "enabled", fallback="").split(",")
                if name.strip()
            ],
            plugin_settings={
                section_name.split(":", 1)[1].strip(): dict(parser.items(section_name))
                for section_name in parser.sections()
                if section_name.startswith("plugin:")
            },
        )
    except (configparser.Error, ValueError) as exc:
        raise ConfigError(f"Invalid settings in {settings_path}: {exc}") from exc

    _validate(settings)
    return settings


def _validate(settings: Settings) -> None:
    if settings.canvas_width <= 0 or settings.canvas_height <= 0:
        raise ConfigError("[output] canvas_width/canvas_height must be positive integers.")

    if settings.fit_mode in ("blurred_image", "sharp_image") and settings.background_image is None:
        raise ConfigError(
            f"[background] fit_mode='{settings.fit_mode}' requires 'background_image' to be set."
        )
    if settings.fit_mode == "blurred_image" and settings.background_image is not None \
            and not settings.background_image.exists():
        raise ConfigError(f"[background] background_image not found: {settings.background_image}")
    if settings.fit_mode == "sharp_image" and settings.background_image is not None \
            and not settings.background_image.exists():
        raise ConfigError(f"[background] background_image not found: {settings.background_image}")

    if settings.fit_mode == "branding_template":
        if settings.branding_template_path is None:
            raise ConfigError(
                "[background] fit_mode='branding_template' requires 'branding_template_path'."
            )
        if not settings.branding_template_path.exists():
            raise ConfigError(
                f"[background] branding_template_path not found: {settings.branding_template_path}"
            )

    if settings.gradient_direction not in ("vertical", "horizontal", "diagonal"):
        raise ConfigError(
            "[background] gradient_direction must be 'vertical', 'horizontal', or 'diagonal'."
        )

    if not (0 <= settings.crf <= 51):
        raise ConfigError("[output] crf must be between 0 and 51.")
