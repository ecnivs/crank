"""
Tests for main.py functionality.
"""

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.app import Core, get_channel_name_from_preset, get_version


class TestMainFunctions:
    """Test suite for main.py utility functions."""

    def test_get_version(self):
        """Test version retrieval from pyproject.toml."""
        version = get_version()
        assert version is not None
        assert isinstance(version, str)
        assert "." in version  # Should be semver format

    def test_get_channel_name_from_preset_success(self, temp_preset_file):
        """Test getting channel name from valid preset."""
        name = get_channel_name_from_preset(str(temp_preset_file))
        assert name == "test_channel"

    def test_get_channel_name_from_preset_missing(self, temp_dir):
        """Test getting channel name from non-existent preset."""
        fake_preset = temp_dir / "missing.yml"
        name = get_channel_name_from_preset(str(fake_preset))
        assert name == "crank"  # Default

    def test_get_channel_name_from_preset_no_name_field(self, temp_dir):
        """Test getting channel name when NAME field is missing."""
        preset_path = temp_dir / "no_name.yml"
        import yaml

        with preset_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump({"OTHER": "value"}, f)

        name = get_channel_name_from_preset(str(preset_path))
        assert name == "crank"  # Default


class TestCore:
    """Test suite for Core class."""

    @patch("src.core.app.Uploader")
    @patch("src.core.app.Editor")
    @patch("src.core.app.Handler")
    @patch("src.core.app.Gemini")
    @patch("src.core.app.Scraper")
    @patch("src.core.app.Orchestrator")
    @patch("src.core.app.genai.Client")
    def test_init_success(
        self,
        mock_client_class,
        mock_orchestrator_class,
        mock_scraper_class,
        mock_gemini_class,
        mock_handler_class,
        mock_editor_class,
        mock_uploader_class,
        temp_preset_file,
        temp_dir,
    ):
        """Test Core initialization with valid preset."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        core = Core(workspace=str(temp_dir), path=str(temp_preset_file))

        assert core.workspace == Path(temp_dir)
        assert core.preset_path == str(temp_preset_file)
        assert core.channel_name == "test_channel"
        assert core.client == mock_client
        assert core.is_running is True

    @patch("src.core.app.Uploader")
    @patch("src.core.app.Editor")
    @patch("src.core.app.Handler")
    @patch("src.core.app.Gemini")
    @patch("src.core.app.Scraper")
    @patch("src.core.app.Orchestrator")
    @patch("src.core.app.genai.Client")
    def test_init_no_api_key(
        self,
        mock_client_class,
        mock_orchestrator_class,
        mock_scraper_class,
        mock_gemini_class,
        mock_handler_class,
        mock_editor_class,
        mock_uploader_class,
        temp_dir,
    ):
        """Test Core initialization without API key."""
        # Create preset without API key
        preset_path = temp_dir / "no_api.yml"
        import yaml

        with preset_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump({"NAME": "test"}, f)

        # Ensure env var is not set
        with patch.dict(os.environ, {}, clear=False):
            if "GEMINI_API_KEY" in os.environ:
                del os.environ["GEMINI_API_KEY"]

            with pytest.raises(RuntimeError, match="GEMINI_API_KEY not found"):
                Core(workspace=str(temp_dir), path=str(preset_path))

    @patch("src.core.app.Uploader")
    @patch("src.core.app.Editor")
    @patch("src.core.app.Handler")
    @patch("src.core.app.Gemini")
    @patch("src.core.app.Scraper")
    @patch("src.core.app.Orchestrator")
    @patch("src.core.app.genai.Client")
    def test_init_upload_disabled(
        self,
        mock_client_class,
        mock_orchestrator_class,
        mock_scraper_class,
        mock_gemini_class,
        mock_handler_class,
        mock_editor_class,
        mock_uploader_class,
        temp_dir,
    ):
        """Test Core initialization with upload disabled."""
        preset_path = temp_dir / "no_upload.yml"
        import yaml

        with preset_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(
                {
                    "NAME": "test",
                    "UPLOAD": False,
                    "GEMINI_API_KEY": "test_key",
                },
                f,
            )

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        core = Core(workspace=str(temp_dir), path=str(preset_path))

        assert core.uploader is None
        assert mock_uploader_class.called is False

    @patch("main.Uploader")
    @patch("main.Editor")
    @patch("main.Handler")
    @patch("main.Gemini")
    @patch("main.Scraper")
    @patch("main.Orchestrator")
    @patch("main.genai.Client")
    def test_time_left_no_limit(
        self,
        mock_client_class,
        mock_orchestrator_class,
        mock_scraper_class,
        mock_gemini_class,
        mock_handler_class,
        mock_editor_class,
        mock_uploader_class,
        temp_preset_file,
        temp_dir,
    ):
        """Test _time_left when no limit is set."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        core = Core(workspace=str(temp_dir), path=str(temp_preset_file))
        time_left = core._time_left()
        assert time_left == 0

    @patch("src.core.app.Uploader")
    @patch("src.core.app.Editor")
    @patch("src.core.app.Handler")
    @patch("src.core.app.Gemini")
    @patch("src.core.app.Scraper")
    @patch("src.core.app.Orchestrator")
    @patch("src.core.app.genai.Client")
    @pytest.mark.asyncio
    async def test_run_keyboard_interrupt(
        self,
        mock_client_class,
        mock_orchestrator_class,
        mock_scraper_class,
        mock_gemini_class,
        mock_handler_class,
        mock_editor_class,
        mock_uploader_class,
        temp_preset_file,
        temp_dir,
    ):
        """Test handling of KeyboardInterrupt in run loop."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_orchestrator = MagicMock()
        mock_orchestrator.process = AsyncMock()
        mock_orchestrator.process.side_effect = KeyboardInterrupt()
        mock_orchestrator_class.return_value = mock_orchestrator

        core = Core(workspace=str(temp_dir), path=str(temp_preset_file))

        # Mock input to trigger prompt
        with (
            patch("builtins.input", return_value="test prompt"),
            patch("src.core.app.print_banner"),
        ):
            with pytest.raises(KeyboardInterrupt):
                await core.run()
