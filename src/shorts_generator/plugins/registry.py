"""
Plugin discovery/registration.

A plugin becomes available by being registered here, and *active* by
being listed in settings.ini's ``[plugins] enabled = ...``. Keeping
"available" and "active" separate means new modules can ship disabled
by default and be turned on per-deployment without a code change.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Type

from ..config import Settings
from .base import RenderPlugin

logger = logging.getLogger("shorts_generator.plugins")

_REGISTRY: Dict[str, Type[RenderPlugin]] = {}


def register_plugin(cls: Type[RenderPlugin]) -> Type[RenderPlugin]:
    """Class decorator: ``@register_plugin`` adds a RenderPlugin subclass to the registry."""
    if not cls.key or cls.key == "base":
        raise ValueError(f"{cls.__name__} must define a unique non-'base' `key`.")
    _REGISTRY[cls.key] = cls
    return cls


def available_plugin_keys() -> List[str]:
    return sorted(_REGISTRY)


def get_enabled_plugins(settings: Settings) -> List[RenderPlugin]:
    """Instantiate every plugin named in settings.ini's [plugins] enabled list.

    Unknown plugin names are logged as a warning and skipped rather than
    raising, so a settings.ini referencing a not-yet-installed future
    module doesn't hard-crash the whole batch.
    """
    instances: List[RenderPlugin] = []
    for name in settings.enabled_plugins:
        cls = _REGISTRY.get(name)
        if cls is None:
            logger.warning(
                "Ignoring unknown plugin '%s' in [plugins] enabled= "
                "(available: %s)", name, ", ".join(available_plugin_keys()) or "none",
            )
            continue
        instances.append(cls.from_settings(settings))
    return instances


# Importing these modules registers the bundled plugins. Neither is
# enabled by default (see settings.ini's [plugins] section) -- ai_metadata
# is a real, usable feature that costs money/needs an API key to run, and
# examples.py exists purely as a working template for future modules to copy.
from . import examples  # noqa: E402,F401  (import for side-effect registration)
from . import ai_metadata  # noqa: E402,F401  (import for side-effect registration)
