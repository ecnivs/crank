"""Abstract base class for background video generation plugins."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict


class BackgroundVideoPlugin(ABC):
    """Abstract base class for background video generation plugins.

    All plugins must inherit from this class and implement the get_media method.
    Plugins are self-contained and load their own configuration from their directory.
    """

    def __init__(self, workspace: Path) -> None:
        """Initialize the plugin with a workspace directory.

        Args:
            workspace: Directory for temporary files and plugin workspace.
        """
        self.workspace: Path = workspace

    @abstractmethod
    def get_media(self, data: Dict[str, Any]) -> Path:
        """Generate and return path to background video.

        Args:
            data: Dictionary containing ALL available pipeline data. Common keys include:
                  - search_term: Search term for video content
                  - transcript: Generated transcript text
                  - title: Video title
                  - description: Video description
                  - categoryId: YouTube category ID
                  Plugins can use ANY fields they need, ignore others, or add custom logic.
                  The app passes everything available - plugins decide what to use.

        Returns:
            Path: Path to processed background video file.
        """
        pass
