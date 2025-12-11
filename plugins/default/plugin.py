"""Default background video plugin using YouTube scraping."""

import logging
import yaml
from pathlib import Path
from typing import Any, Dict

from src.plugins.base import BackgroundVideoPlugin

from .scraper import YouTubeScraper
from .processor import VideoProcessor


class DefaultPlugin(BackgroundVideoPlugin):
    """Default plugin that uses YouTube scraping for background video generation.

    This plugin extracts the search_term from the data dictionary and uses
    YouTube scraping to download and process videos.
    """

    def __init__(self, workspace: Path) -> None:
        """Initialize the default plugin.

        Args:
            workspace: Directory for temporary files and plugin workspace.
        """
        super().__init__(workspace)
        self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)
        self.workspace.mkdir(exist_ok=True)
        self.config: Dict[str, Any] = self._load_config()
        
        self.processor: VideoProcessor = VideoProcessor(workspace=self.workspace)
        self.scraper: YouTubeScraper = YouTubeScraper(
            workspace=self.workspace,
            config=self.config,
            processor=self.processor,
        )

    def _load_config(self) -> Dict[str, Any]:
        """Load plugin configuration from config.yml in plugin directory.

        Returns:
            Dictionary containing plugin configuration.
        """
        config_file = Path(__file__).parent / "config.yml"
        if config_file.exists():
            try:
                with config_file.open("r", encoding="utf-8") as f:
                    config = yaml.safe_load(f) or {}
                    self.logger.info(f"Loaded config from {config_file}")
                    return config
            except Exception as e:
                self.logger.warning(
                    f"Failed to load config from {config_file}: {e}. Using defaults."
                )
        else:
            self.logger.info(
                f"Config file not found at {config_file}. Using defaults."
            )
        return {}

    def get_media(self, data: Dict[str, Any]) -> Path:
        """Generate and return path to background video.

        Extracts search_term from the data dictionary and uses YouTube scraping
        to download and process a video.

        Args:
            data: Dictionary containing pipeline data. This plugin uses:
                  - search_term: Search term for YouTube video content

        Returns:
            Path: Path to processed background video file.
        """
        search_term = data.get("search_term", "")
        if not search_term:
            self.logger.warning(
                "No search_term found in data dictionary. Using empty string."
            )

        max_results = self.config.get("max_results", 10)
        self.logger.debug(f"Getting media for search term: {search_term}")
        
        video_path: Path = self.scraper.download_video(search_term, max_results)
        short_path: Path = self.processor.process_to_short(video_path)
        video_path.unlink(missing_ok=True)
        self.logger.info(f"Video template stored at {short_path}")
        return short_path
