"""
Maps a settings.ini ``fit_mode`` string to its :class:`BackgroundMode`
implementation.

This is the single place that needs a new line added when a brand-new
fit mode is introduced -- see ``base.py`` for the extension contract
each mode must satisfy.
"""

from __future__ import annotations

from ..config import Settings
from ..exceptions import BackgroundModeError
from ..utils.video_info import VideoInfo
from .base import BackgroundMode
from .auto_blur_video import AutoBlurVideoBackground
from .blurred_image import BlurredImageBackground
from .branding_template import BrandingTemplateBackground
from .gradient import GradientBackground
from .sharp_image import SharpImageBackground
from .solid_color import SolidColorBackground
from .split_top_bottom import SplitTopBottomBackground

_REGISTRY = {
    cls.key: cls
    for cls in (
        BlurredImageBackground,
        SharpImageBackground,
        SolidColorBackground,
        GradientBackground,
        AutoBlurVideoBackground,
        SplitTopBottomBackground,
        BrandingTemplateBackground,
    )
}


def get_background_mode(settings: Settings, video_info: VideoInfo) -> BackgroundMode:
    cls = _REGISTRY.get(settings.fit_mode)
    if cls is None:
        raise BackgroundModeError(
            f"Unknown fit_mode '{settings.fit_mode}'. "
            f"Available modes: {', '.join(sorted(_REGISTRY))}"
        )
    return cls(settings, video_info)
