import logging
import random
import re
import time
from google.genai import types
from google import genai
from google.genai.errors import ClientError
import wave
import os
from pathlib import Path
from typing import Union, Dict, Optional, List
from utils.constants import GEMINI_MODELS, DEFAULT_VOICE


class QuotaExceededError(RuntimeError):
    """Exception raised when API quota is exceeded after all retries."""

    pass


class Gemini:
    """Handles Gemini API interactions for text and audio generation."""

    def __init__(self, client: genai.Client, workspace: Union[str, Path]) -> None:
        """
        Initialize Gemini client.

        Args:
            client: Google Gemini API client.
            workspace: Directory for temporary files.
        """
        self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)
        self.client: genai.Client = client
        self.workspace: Union[str, Path] = workspace
        self.models: Dict[str, str] = GEMINI_MODELS
        self.voice: str = DEFAULT_VOICE

    def _extract_retry_delay(self, error: Exception) -> float:
        """
        Extract retry delay from 429 quota error response.

        Args:
            error: Exception that may contain retry delay information.

        Returns:
            float: Retry delay in seconds, or 60.0 as default.
        """
        default_delay = 60.0

        if isinstance(error, ClientError):
            try:
                error_str = str(error)
                retry_delay_match = re.search(r"Please retry in ([\d.]+)s", error_str)
                if retry_delay_match:
                    delay = float(retry_delay_match.group(1))
                    return max(delay, 5.0)

                retry_delay_alt = re.search(r"retryDelay[=:] ['\"]?(\d+)s", error_str)
                if retry_delay_alt:
                    delay = float(retry_delay_alt.group(1))
                    return max(delay, 5.0)
            except (ValueError, AttributeError, IndexError):
                pass

        return default_delay

    def _is_quota_exceeded(self, error: Exception) -> bool:
        """
        Check if error is due to quota exhaustion.

        Args:
            error: Exception to check.

        Returns:
            bool: True if error is a 429 quota error.
        """
        if isinstance(error, ClientError):
            error_str = str(error)
            return "429" in error_str and "RESOURCE_EXHAUSTED" in error_str
        return False

    def _save_to_wav(self, pcm: bytes) -> str:
        """
        Save PCM audio data to WAV file.

        Args:
            pcm: Raw PCM audio bytes.

        Returns:
            str: Path to saved WAV file.
        """
        path = os.path.join(str(self.workspace), "speech.wav")

        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(32000)
            wf.writeframes(pcm)
        return path

    def get_audio(self, transcript: str) -> str:
        """
        Generate speech audio from transcript using TTS.

        Args:
            transcript: Text to convert to speech.

        Returns:
            str: Path to generated audio file.

        Raises:
            QuotaExceededError: If daily quota is exceeded.
            RuntimeError: If audio generation fails.
        """
        if not transcript:
            raise ValueError("Transcript must be a non-empty string")

        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash-preview-tts",
                contents=transcript,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=self.voice,
                            )
                        )
                    ),
                ),
            )

            if not response.candidates:
                raise ValueError("No candidates returned from TTS model")
            if not response.candidates[0].content.parts:
                raise ValueError("No content parts returned in response")

            data = response.candidates[0].content.parts[0].inline_data.data
            if not data:
                raise ValueError("No audio data found in response")

            path = self._save_to_wav(data)
            self.logger.info(f"Audio saved to {path}")
            return path

        except Exception as e:
            if self._is_quota_exceeded(e):
                raise QuotaExceededError(
                    "Daily API quota exceeded. Please wait 24 hours before trying again or check your billing plan."
                )
            else:
                raise RuntimeError(
                    f"Failed to generate audio from transcript. "
                    f"Error: {e}\n"
                    f"Please check your API key and ensure the transcript is valid."
                ) from e

    def get_response(
        self, query: str, model: Union[str, float], max_retries: int = 3
    ) -> Optional[str]:
        """
        Generate text response from Gemini API with fallback retry logic.

        Args:
            query: Prompt string.
            model: Model version (2.5 or 2.0).
            max_retries: Maximum retry attempts per model.

        Returns:
            Optional[str]: Generated text or None if all attempts fail.
        """
        current_model: Optional[str] = self.models.get(str(model))

        if not current_model:
            self.logger.error(f"Model '{model}' not found in self.models")
            return None

        models_priority: List[str] = list(self.models.values())
        start_index: int = models_priority.index(current_model)

        for model_index in range(start_index, len(models_priority)):
            fallback_model = models_priority[model_index]

            for attempt in range(1, max_retries + 1):
                try:
                    response = self.client.models.generate_content(
                        model=fallback_model, contents=query
                    )

                    text = getattr(response, "text", None)
                    if not text:
                        raise ValueError(f"No text in Gemini response: {response}")

                    self.logger.info(
                        f"Gemini returned (model={fallback_model}): {text}"
                    )
                    return text

                except Exception as e:
                    if self._is_quota_exceeded(e):
                        raise QuotaExceededError(
                            "Daily API quota exceeded. Please wait 24 hours before trying again or check your billing plan."
                        )
                    else:
                        wait = 2**attempt + random.uniform(0, 1)
                        self.logger.warning(
                            f"Attempt {attempt}/{max_retries} with {fallback_model} failed: {e}. Retrying in {wait:.1f}s"
                        )
                        time.sleep(wait)

            self.logger.warning(
                f"Model {fallback_model} exhausted retries, trying fallback if available"
            )

        raise RuntimeError("All Gemini models failed after retries and fallbacks")
