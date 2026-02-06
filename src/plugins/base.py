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
                  - audio_path: Path to generated audio file
                  - captions_path: Path to generated .ass subtitle file
                  - caption_data: Dict with transcription segments and word-level timestamps
                  Plugins can use ANY fields they need, ignore others, or add custom logic.
                  The app passes everything available - plugins decide what to use.

        Returns:
            Union[Path, Dict[str, Any]]: Path to video file, OR a dict containing:
                - video_path: Path to video file (Required)
                - audio_path: Path to background audio file (Optional)
                - config: Dict with keys like 'suppress_captions' (Optional)
        """
        pass

    def get_prompt_context(self, topic: str) -> str:
        """
        Get custom instructions to inject into the LLM prompt.

        Args:
            topic: The user's requested topic.

        Returns:
            str: Additional instructions for the LLM (e.g., tone, formatting).
        """
        return ""
