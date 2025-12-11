"""Plugin system for background video generation."""

from src.plugins.base import BackgroundVideoPlugin
from src.plugins.registry import PluginRegistry

__all__ = ["BackgroundVideoPlugin", "PluginRegistry"]
