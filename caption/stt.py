import whisper
import logging
from pathlib import Path
from typing import Dict, Any


class SpeechToText:
    """
    Wrapper for OpenAI's Whisper model to perform speech-to-text transcription.
    """

    def __init__(self, model_size: str) -> None:
        """
        Initialize the Whisper model for transcription.

        Args:
            model_size: Size of the Whisper model to load (e.g., 'tiny', 'base', 'small', 'medium', 'large').
        """
        self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)
        self.model: whisper.Whisper = whisper.load_model(model_size)

    def transcribe(self, audio_path: Path | str) -> Dict[str, Any]:
        """
        Transcribe an audio file into text with word-level timestamps.

        Args:
            audio_path: Path to the audio file to transcribe.

        Returns:
            Dict[str, Any]: Whisper transcription output, including 'text', 'segments', and word timestamps.
        """
        self.logger.info(f"Transcribing audio file: {audio_path}")
        result: Dict[str, Any] = self.model.transcribe(
            str(audio_path), word_timestamps=True
        )
        self.logger.info(f"Transcription completed for: {audio_path}")
        return result

