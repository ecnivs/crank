from faster_whisper import WhisperModel
import logging
from pathlib import Path
from typing import Dict, Any, List, Union
import torch


class SpeechToText:
    """Wrapper for faster-whisper model to perform speech-to-text transcription."""

    def __init__(self, model_size: str) -> None:
        """
        Initialize faster-whisper model.

        Args:
            model_size: Model size (e.g., 'tiny', 'base', 'small', 'medium', 'large-v2').
        """
        self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)

        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model: WhisperModel = WhisperModel(
            model_size, device=device, compute_type="float16"
        )

    def transcribe(self, audio_path: Union[Path, str]) -> Dict[str, Any]:
        """
        Transcribe an audio file into text with word-level timestamps.

        Args:
            audio_path: Path to the audio file to transcribe.

        Returns:
            Dict[str, Any]: Transcription output with 'text' and 'segments' keys.
        """
        self.logger.info(f"Transcribing audio file: {audio_path}")
        segments, info = self.model.transcribe(str(audio_path), word_timestamps=True)

        result_segments: List[Dict[str, Any]] = []
        full_text = ""

        for segment in segments:
            words = [
                {"word": w.word, "start": w.start, "end": w.end}
                for w in (segment.words or [])
            ]

            result_segments.append(
                {
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip(),
                    "words": words,
                }
            )
            full_text += segment.text.strip() + " "

        self.logger.info(f"Transcription completed for: {audio_path}")

        return {
            "text": full_text.strip(),
            "segments": result_segments,
            "language": info.language,
            "duration": info.duration,
        }
