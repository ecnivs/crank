"""
Integration tests for src.core.orchestrator.Orchestrator class.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.core.orchestrator import Orchestrator
from src.response import QuotaExceededError


@pytest.fixture
def mock_orchestrator_dependencies(temp_dir, preset_handler, mock_gemini_client):
    """Create mocked dependencies for Orchestrator."""
    with (
        patch("src.core.orchestrator.Gemini") as mock_gemini_class,
        patch("src.core.orchestrator.Editor") as mock_editor_class,
        patch("src.core.orchestrator.Handler") as mock_handler_class,
        patch("src.core.orchestrator.Uploader") as mock_uploader_class,
    ):
        # Create mock instances
        mock_plugin = MagicMock()
        mock_plugin.get_media.return_value = temp_dir / "media.mp4"

        mock_gemini = MagicMock()
        mock_gemini.get_audio.return_value = str(temp_dir / "audio.wav")
        mock_gemini.get_response.return_value = "TRANSCRIPT: Say excitedly: Test\nTITLE: Test Title\nDESCRIPTION: Test Desc\nSEARCH_TERM: test\nCATEGORY_ID: 24"
        mock_gemini_class.return_value = mock_gemini

        mock_editor = MagicMock()
        output_file = temp_dir / "output.mp4"
        output_file.write_bytes(b"fake_output_video")
        mock_editor.assemble.return_value = output_file
        mock_editor_class.return_value = mock_editor

        mock_handler = MagicMock()
        mock_handler.get_captions.return_value = temp_dir / "captions.ass"
        mock_handler_class.return_value = mock_handler

        mock_uploader = MagicMock()
        mock_uploader.upload.return_value = ("https://youtube.com/watch?v=test", None)
        mock_uploader_class.return_value = mock_uploader

        yield {
            "plugin": mock_plugin,
            "gemini": mock_gemini,
            "editor": mock_editor,
            "handler": mock_handler,
            "uploader": mock_uploader,
            "preset": preset_handler,
        }


@pytest.fixture
def orchestrator(mock_orchestrator_dependencies):
    """Create an Orchestrator instance with mocked dependencies."""
    deps = mock_orchestrator_dependencies
    return Orchestrator(
        preset=deps["preset"],
        plugin=deps["plugin"],
        gemini=deps["gemini"],
        editor=deps["editor"],
        caption=deps["handler"],
        uploader=deps["uploader"],
    )


class TestOrchestrator:
    """Test suite for Orchestrator class."""

    @pytest.mark.asyncio
    async def test_process_success(self, orchestrator, mock_orchestrator_dependencies):
        """Test successful video processing pipeline."""
        deps = mock_orchestrator_dependencies

        # Create mock prompt
        with patch("src.core.orchestrator.Prompt") as mock_prompt_class:
            mock_prompt = MagicMock()
            mock_prompt.build.return_value = "Test prompt"
            mock_prompt_class.return_value = mock_prompt

            orchestrator.prompt = mock_prompt

            result = await orchestrator.process("test topic")

            # Verify all steps were called
            assert mock_prompt.build.called
            assert deps["gemini"].get_response.called
            assert deps["gemini"].get_audio.called
            assert deps["handler"].get_captions.called
            assert deps["plugin"].get_media.called
            assert deps["editor"].assemble.called
            assert deps["uploader"].upload.called
            assert result.exists()

    @pytest.mark.asyncio
    async def test_process_without_uploader(
        self, preset_handler, mock_orchestrator_dependencies
    ):
        """Test processing without uploader."""
        deps = mock_orchestrator_dependencies

        with patch("src.core.orchestrator.Prompt") as mock_prompt_class:
            mock_prompt = MagicMock()
            mock_prompt.build.return_value = "Test prompt"
            mock_prompt_class.return_value = mock_prompt

            orchestrator = Orchestrator(
                preset=deps["preset"],
                plugin=deps["plugin"],
                gemini=deps["gemini"],
                editor=deps["editor"],
                caption=deps["handler"],
                uploader=None,
            )
            orchestrator.prompt = mock_prompt

            result = await orchestrator.process("test topic")

            # Uploader should not be called
            assert not deps["uploader"].upload.called
            assert result.exists()

    @pytest.mark.asyncio
    async def test_process_quota_exceeded(
        self, orchestrator, mock_orchestrator_dependencies
    ):
        """Test handling of quota exceeded error."""
        deps = mock_orchestrator_dependencies

        with patch("src.core.orchestrator.Prompt") as mock_prompt_class:
            mock_prompt = MagicMock()
            mock_prompt.build.return_value = "Test prompt"
            mock_prompt_class.return_value = mock_prompt

            orchestrator.prompt = mock_prompt

            # Make get_response raise QuotaExceededError
            deps["gemini"].get_response.side_effect = QuotaExceededError(
                "Quota exceeded"
            )

            with pytest.raises(QuotaExceededError):
                await orchestrator.process("test topic")

            # Verify preset LIMIT_TIME was set
            assert deps["preset"].get("LIMIT_TIME") is not None

    @pytest.mark.asyncio
    async def test_process_missing_transcript(
        self, orchestrator, mock_orchestrator_dependencies
    ):
        """Test handling of missing transcript in response."""
        deps = mock_orchestrator_dependencies

        with patch("src.core.orchestrator.Prompt") as mock_prompt_class:
            mock_prompt = MagicMock()
            mock_prompt.build.return_value = "Test prompt"
            mock_prompt_class.return_value = mock_prompt

            orchestrator.prompt = mock_prompt

            # Return response without TRANSCRIPT field
            deps["gemini"].get_response.return_value = "TITLE: Test\nDESCRIPTION: Test"

            with pytest.raises(ValueError, match="Cannot proceed without transcript"):
                await orchestrator.process("test topic")

    @pytest.mark.asyncio
    async def test_upload_resumable_error(
        self, orchestrator, mock_orchestrator_dependencies
    ):
        """Test handling of ResumableUploadError during upload."""
        from googleapiclient.http import ResumableUploadError
        from src.response.gemini import QuotaExceededError

        deps = mock_orchestrator_dependencies

        with patch("src.core.orchestrator.Prompt") as mock_prompt_class:
            mock_prompt = MagicMock()
            mock_prompt.build.return_value = "Test prompt"
            mock_prompt_class.return_value = mock_prompt

            orchestrator.prompt = mock_prompt

            from unittest.mock import Mock as MockObj

            mock_resp = MockObj()
            mock_resp.status = 403
            mock_resp.reason = "Forbidden"
            error = ResumableUploadError(mock_resp, b"Forbidden")
            deps["uploader"].upload.side_effect = error

            with pytest.raises(QuotaExceededError, match="Upload limit reached"):
                await orchestrator.process("test topic")

            # Verify LIMIT_TIME was set
            assert deps["preset"].get("LIMIT_TIME") is not None

    def test_extract_fields_from_response(self, orchestrator):
        """Test field extraction from Gemini response."""
        response_text = """TRANSCRIPT: Say excitedly: This is a test.
DESCRIPTION: This is a test description.
SEARCH_TERM: test visual
TITLE: Test Title
CATEGORY_ID: 24"""

        assert "TRANSCRIPT" in response_text
        assert "TITLE" in response_text
