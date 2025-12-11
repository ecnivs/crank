"""Plugin registry for discovering and loading background video plugins."""

import importlib.util
import logging
from pathlib import Path
from typing import Dict, Optional, Type

from src.plugins.base import BackgroundVideoPlugin


class PluginRegistry:
    """Discovers and manages background video generation plugins."""

    def __init__(self, plugins_dir: Path) -> None:
        """Initialize the plugin registry.

        Args:
            plugins_dir: Directory containing plugin subdirectories.
        """
        self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)
        self.plugins_dir: Path = plugins_dir
        self._plugin_classes: Dict[str, Type[BackgroundVideoPlugin]] = {}
        self._discover_plugins()

    def _discover_plugins(self) -> None:
        """Discover all plugins in the plugins directory."""
        if not self.plugins_dir.exists():
            self.logger.warning(f"Plugins directory does not exist: {self.plugins_dir}")
            return

        for plugin_dir in self.plugins_dir.iterdir():
            if not plugin_dir.is_dir():
                continue

            plugin_name = plugin_dir.name
            plugin_file = plugin_dir / "plugin.py"

            if not plugin_file.exists():
                self.logger.debug(f"Skipping {plugin_dir}: no plugin.py found")
                continue

            try:
                plugin_class = self._load_plugin_class(plugin_file, plugin_name)
                if plugin_class:
                    self._plugin_classes[plugin_name] = plugin_class
                    self.logger.info(f"Discovered plugin: {plugin_name}")
            except Exception as e:
                self.logger.error(
                    f"Failed to load plugin from {plugin_file}: {e}", exc_info=True
                )

    def _load_plugin_class(
        self, plugin_file: Path, plugin_name: str
    ) -> Optional[Type[BackgroundVideoPlugin]]:
        """Load a plugin class from a plugin file.

        Args:
            plugin_file: Path to the plugin.py file.
            plugin_name: Name of the plugin (directory name).

        Returns:
            Plugin class if found and valid, None otherwise.
        """
        spec = importlib.util.spec_from_file_location(
            f"plugins.{plugin_name}.plugin", plugin_file
        )
        if spec is None or spec.loader is None:
            self.logger.error(f"Failed to create spec for {plugin_file}")
            return None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        plugin_class = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, BackgroundVideoPlugin)
                and attr is not BackgroundVideoPlugin
                and attr_name.endswith("Plugin")
            ):
                plugin_class = attr
                break

        if plugin_class is None:
            self.logger.error(
                f"No plugin class found in {plugin_file}. "
                f"Expected a class ending with 'Plugin' inheriting from BackgroundVideoPlugin"
            )
            return None

        return plugin_class

    def get_plugin(
        self, plugin_name: str, workspace: Path
    ) -> Optional[BackgroundVideoPlugin]:
        """Get an instance of a plugin.

        Args:
            plugin_name: Name of the plugin to load.
            workspace: Workspace directory for the plugin.

        Returns:
            Plugin instance if found, None otherwise.
        """
        if plugin_name not in self._plugin_classes:
            self.logger.error(f"Plugin '{plugin_name}' not found")
            return None

        plugin_class = self._plugin_classes[plugin_name]
        try:
            plugin_instance = plugin_class(workspace)
            self.logger.info(f"Loaded plugin instance: {plugin_name}")
            return plugin_instance
        except Exception as e:
            self.logger.error(
                f"Failed to instantiate plugin '{plugin_name}': {e}", exc_info=True
            )
            return None

    def list_plugins(self) -> list[str]:
        """List all discovered plugin names.

        Returns:
            List of plugin names.
        """
        return list(self._plugin_classes.keys())

    def has_plugin(self, plugin_name: str) -> bool:
        """Check if a plugin exists.

        Args:
            plugin_name: Name of the plugin to check.

        Returns:
            True if plugin exists, False otherwise.
        """
        return plugin_name in self._plugin_classes
