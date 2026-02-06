
import pytest
from unittest.mock import MagicMock, patch
from src.core.orchestrator import Orchestrator

@pytest.mark.asyncio
async def test_prompt_injection_flow(temp_dir, preset_handler):
    """Verify plugin prompt instruction is retrieved and used."""
    with (
        patch("src.core.orchestrator.Gemini") as mock_gemini_class,
        patch("src.core.orchestrator.Editor") as mock_editor_class,
        patch("src.core.orchestrator.Handler") as mock_handler_class,
        patch("src.core.orchestrator.Uploader") as mock_uploader_class,
        patch("src.core.orchestrator.Prompt") as mock_prompt_class,
    ):
        mock_plugin = MagicMock()
        mock_plugin.get_media.return_value = temp_dir / "video.mp4"
        # The key: Plugin returns an instruction
        mock_plugin.get_prompt_context.return_value = "USE SCARY TONE"

        mock_gemini = MagicMock()
        mock_gemini.get_audio.return_value = temp_dir / "voice.wav"
        mock_gemini.get_response.return_value = "TRANSCRIPT: Boo\nTITLE: Scary"
        mock_gemini_class.return_value = mock_gemini
        
        mock_editor = MagicMock()
        mock_editor.assemble.return_value = temp_dir / "out.mp4"
        mock_editor_class.return_value = mock_editor
        
        mock_handler = MagicMock()
        mock_handler.get_captions.return_value = (temp_dir / "captions.ass", {})
        mock_handler_class.return_value = mock_handler
        
        mock_prompt = MagicMock()
        mock_prompt.build.return_value = "FINAL PROMPT"
        mock_prompt_class.return_value = mock_prompt

        orchestrator = Orchestrator(
            preset=preset_handler,
            plugin=mock_plugin,
            gemini=mock_gemini,
            editor=mock_editor,
            caption=mock_handler,
            uploader=None
        )

        user_topic = "Haunted House"
        await orchestrator.process(user_topic)

        # Verify plugin was asked for context
        mock_plugin.get_prompt_context.assert_called_once_with(user_topic)
        
        # Verify prompt.build received the instruction
        mock_prompt.build.assert_called_once()
        call_kwargs = mock_prompt.build.call_args.kwargs
        call_args = mock_prompt.build.call_args.args
        
        # Check args
        assert call_args[0] == user_topic
        assert call_kwargs.get("plugin_instruction") == "USE SCARY TONE"
