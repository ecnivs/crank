
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from src.core.orchestrator import Orchestrator

@pytest.mark.asyncio
async def test_plugin_receives_enhanced_data(temp_dir, preset_handler):
    """Verify that the plugin receives audio_path, captions_path, and caption_data."""
    
    # Mock dependencies
    with (
        patch("src.core.orchestrator.Gemini") as mock_gemini_class,
        patch("src.core.orchestrator.Editor") as mock_editor_class,
        patch("src.core.orchestrator.Handler") as mock_handler_class,
        patch("src.core.orchestrator.Uploader") as mock_uploader_class,
        patch("src.core.orchestrator.Prompt") as mock_prompt_class,
    ):
        # Setup mocks
        mock_plugin = MagicMock()
        mock_plugin.get_media.return_value = temp_dir / "media.mp4"

        mock_gemini = MagicMock()
        mock_gemini.get_audio.return_value = temp_dir / "audio.wav"
        # Return a response that includes TRANSCRIPT so we don't trigger errors
        mock_gemini.get_response.return_value = "TRANSCRIPT: Say hello.\nTITLE: Test\nDESCRIPTION: Test\nSEARCH_TERM: test"
        mock_gemini_class.return_value = mock_gemini

        mock_editor = MagicMock()
        mock_editor.assemble.return_value = temp_dir / "output.mp4"
        mock_editor_class.return_value = mock_editor

        mock_handler = MagicMock()
        fake_caption_data = {"segments": [{"text": "hello", "start": 0, "end": 1}]}
        mock_handler.get_captions.return_value = (temp_dir / "captions.ass", fake_caption_data)
        mock_handler_class.return_value = mock_handler
        
        mock_prompt = MagicMock()
        mock_prompt.build.return_value = "prompt"
        mock_prompt_class.return_value = mock_prompt

        # Initialize Orchestrator
        orchestrator = Orchestrator(
            preset=preset_handler,
            plugin=mock_plugin,
            gemini=mock_gemini,
            editor=mock_editor,
            caption=mock_handler,
            uploader=None
        )
        orchestrator.prompt = mock_prompt

        # Run process
        await orchestrator.process("test input")

        # Verify plugin.get_media was called
        assert mock_plugin.get_media.called
        
        # Verify arguments passed to get_media
        call_args = mock_plugin.get_media.call_args
        assert call_args is not None
        passed_data = call_args[0][0]  # First arg is 'data' dict
        
        # Check for new fields
        assert "audio_path" in passed_data
        assert passed_data["audio_path"] == str(temp_dir / "audio.wav")
        
        assert "captions_path" in passed_data
        assert passed_data["captions_path"] == str(temp_dir / "captions.ass")
        
        assert "caption_data" in passed_data
        assert passed_data["caption_data"] == fake_caption_data

@pytest.mark.asyncio
async def test_plugin_returns_dict_with_config(temp_dir, preset_handler):
    """Verify orchestrator handles dict return with audio and config."""
    with (
        patch("src.core.orchestrator.Gemini") as mock_gemini_class,
        patch("src.core.orchestrator.Editor") as mock_editor_class,
        patch("src.core.orchestrator.Handler") as mock_handler_class,
        patch("src.core.orchestrator.Uploader") as mock_uploader_class,
        patch("src.core.orchestrator.Prompt") as mock_prompt_class,
    ):
        mock_plugin = MagicMock()
        video_path = temp_dir / "video.mp4"
        audio_path = temp_dir / "bg_audio.mp3"
        mock_plugin.get_media.return_value = {
            "video_path": video_path,
            "audio_path": audio_path,
            "config": {"suppress_captions": True}
        }

        mock_gemini = MagicMock()
        mock_gemini.get_audio.return_value = temp_dir / "voice.wav"
        mock_gemini.get_response.return_value = "TRANSCRIPT: Hello"
        mock_gemini_class.return_value = mock_gemini

        mock_editor = MagicMock()
        mock_editor.assemble.return_value = temp_dir / "output.mp4"
        mock_editor_class.return_value = mock_editor

        mock_handler = MagicMock()
        mock_handler.get_captions.return_value = (temp_dir / "captions.ass", {})
        mock_handler_class.return_value = mock_handler
        
        mock_prompt = MagicMock()
        mock_prompt.build.return_value = "prompt"
        mock_prompt_class.return_value = mock_prompt

        orchestrator = Orchestrator(
            preset=preset_handler,
            plugin=mock_plugin,
            gemini=mock_gemini,
            editor=mock_editor,
            caption=mock_handler,
            uploader=None
        )
        orchestrator.prompt = mock_prompt

        await orchestrator.process("test")

        # Verify assemble called with correct extra args
        mock_editor.assemble.assert_called_once()
        call_kwargs = mock_editor.assemble.call_args.kwargs
        # If passed as positional, check args
        call_args = mock_editor.assemble.call_args.args
        
        # Check args based on signature: ass, audio, media, bg_audio, suppress
        assert call_args[2] == video_path # media_path
        assert call_args[3] == audio_path # background_audio_path
        assert call_args[4] is True # suppress_captions
