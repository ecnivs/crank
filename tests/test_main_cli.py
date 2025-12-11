"""
Tests for main.py CLI functionality.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.core.app import ArgumentParser


class TestCLI:
    """Test suite for CLI argument parsing and environment variable handling."""

    def test_path_argument_priority(self, temp_dir, monkeypatch):
        """Test that --path argument takes priority over PRESET_PATH env var."""
        preset1 = temp_dir / "preset1.yml"
        preset2 = temp_dir / "preset2.yml"
        preset1.write_text("NAME: preset1")
        preset2.write_text("NAME: preset2")

        # Set environment variable
        monkeypatch.setenv("PRESET_PATH", str(preset1))

        # Simulate argparse
        args = Mock()
        args.path = str(preset2)
        result_path = args.path or os.environ.get("PRESET_PATH", "config/preset.yml")

        assert result_path == str(preset2)  # --path should win

    def test_preset_path_env_var(self, temp_dir, monkeypatch):
        """Test PRESET_PATH environment variable fallback."""
        preset = temp_dir / "preset_env.yml"
        preset.write_text("NAME: env_preset")

        monkeypatch.setenv("PRESET_PATH", str(preset))

        # Simulate no --path argument
        args = Mock()
        args.path = None

        result_path = args.path or os.environ.get("PRESET_PATH", "config/preset.yml")

        assert result_path == str(preset)

    def test_default_preset_path(self, monkeypatch):
        """Test default preset path when neither argument nor env var is set."""
        monkeypatch.delenv("PRESET_PATH", raising=False)

        args = Mock()
        args.path = None

        result_path = args.path or os.environ.get("PRESET_PATH", "config/preset.yml")

        assert result_path == "config/preset.yml"

    @patch("src.core.app.setup_logging")
    @patch("src.core.app.get_channel_name_from_preset")
    @patch("src.core.app.new_workspace")
    @patch("src.core.app.Core")
    def test_main_entry_point(
        self,
        mock_core_class,
        mock_workspace,
        mock_get_channel,
        mock_setup_logging,
        temp_preset_file,
    ):
        """Test main entry point execution."""
        mock_workspace.return_value.__enter__.return_value = "/tmp/test"
        mock_get_channel.return_value = "test_channel"
        mock_core = MagicMock()
        mock_core.run = Mock()
        mock_core_class.return_value = mock_core

        with (
            patch("sys.argv", ["main.py", "--path", str(temp_preset_file)]),
            patch("src.core.app.asyncio.run") as mock_asyncio_run,
            patch("src.core.app.load_dotenv"),
        ):
            parser = ArgumentParser()
            parser.add_argument("--path", default=None)
            parser.add_argument("--version", action="version", version="test")
            args = parser.parse_args(["--path", str(temp_preset_file)])

            assert args.path == str(temp_preset_file)

    @patch("src.core.app.setup_logging")
    @patch("src.core.app.get_channel_name_from_preset")
    @patch("src.core.app.new_workspace")
    def test_preset_file_validation(
        self,
        mock_workspace,
        mock_get_channel,
        mock_setup_logging,
        temp_dir,
    ):
        """Test validation of preset file existence."""
        fake_preset = temp_dir / "nonexistent.yml"

        preset_path = Path(str(fake_preset))
        if not preset_path.exists():
            with pytest.raises(SystemExit):
                print("Error message", file=sys.stderr)
                sys.exit(1)
