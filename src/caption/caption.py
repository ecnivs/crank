import logging
import spacy
from .stt import SpeechToText
from pathlib import Path
from typing import List, Dict, Union, Any

try:
    import en_core_web_md
    SPACY_MODEL_AVAILABLE = True
except ImportError:
    SPACY_MODEL_AVAILABLE = False


class Handler:
    """
    Generates ASS subtitles.
    """

    def __init__(self, workspace: Path, model_size: str, font: str) -> None:
        """
        Initialize the caption handler.

        Args:
            workspace: Path to store generated captions.
            model_size: Size of Whisper model to load for transcription.
            font: Font name to use in ASS subtitle styling.
        """
        self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)
        self.workspace: Path = workspace
        self.workspace.mkdir(exist_ok=True)

        self.stt: SpeechToText = SpeechToText(model_size)
        self.font: str = font
        
        if SPACY_MODEL_AVAILABLE:
            self.nlp = en_core_web_md.load(disable=["ner", "lemmatizer"])
        else:
            try:
                self.nlp = spacy.load("en_core_web_md", disable=["ner", "lemmatizer"])
            except OSError:
                raise RuntimeError(
                    "spaCy model 'en_core_web_md' not found. "
                    "Please install it with: uv run python -m spacy download en_core_web_md"
                )

        self.header: str = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Dynamic, {self.font}, 48, &H00FFFFFF, &H000000FF, &H00000000, &H80000000, 1, 0, 0, 0, 100, 100, 0, 0, 1, 2, 0, 5, 50, 50, 20, 1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def _format_timestamp(self, ts: float) -> str:
        """
        Convert seconds to ASS timestamp format (h:mm:ss.cs).

        Args:
            ts: Time in seconds.

        Returns:
            str: Formatted timestamp.
        """
        h = int(ts // 3600)
        m = int((ts % 3600) // 60)
        s = int(ts % 60)
        cs = int((ts - int(ts)) * 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    def _apply_pos_coloring(self, words: List[str]) -> List[str]:
        """
        Apply color tags to words based on part-of-speech.

        Args:
            words: List of words in a segment.

        Returns:
            List[str]: Words with ASS color formatting applied.
        """
        text = " ".join(words)
        doc = self.nlp(text)

        colored_words: List[str] = []
        for token in doc:
            if token.pos_ == "VERB":
                colored_words.append(r"{\c&HD8BFD8&}" + token.text)
            elif token.pos_ == "PRON":
                colored_words.append(r"{\c&FFDAB9&}" + token.text)
            else:
                colored_words.append(token.text)

        return colored_words

    def get_captions(self, audio_path: Union[str, Path]) -> Path:
        """
        Generate ASS captions from audio file.

        Args:
            audio_path: Path to audio file to transcribe.

        Returns:
            Path: Path to the generated ASS file.

        Raises:
            FileNotFoundError: If audio file does not exist.
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(
                f"Audio file not found: {audio_path}\n"
                f"Please ensure the audio file exists and the path is correct."
            )
        result: Dict[str, Any] = self.stt.transcribe(audio_path)
        path: Path = self.workspace / "captions.ass"

        with open(path, "w", encoding="utf-8") as f:
            f.write(self.header)

            for segment in result.get("segments", []):
                words_data = segment.get("words", [])

                if not words_data:
                    start = self._format_timestamp(segment["start"])
                    end = self._format_timestamp(segment["end"])
                    text = segment["text"].strip()
                    f.write(f"Dialogue: 0,{start},{end},Dynamic,,0,0,0,,{text}\n")
                    continue

                i = 0
                while i < len(words_data):
                    current_word = words_data[i]["word"].strip()
                    if len(current_word) > 8:
                        chunk_size = 1
                    else:
                        chunk_size = 1
                        total_chars = len(current_word)

                        for j in range(i + 1, min(i + 2, len(words_data))):
                            next_word = words_data[j]["word"].strip()
                            if total_chars + len(next_word) + 1 > 20:
                                break
                            if len(next_word) > 8:
                                break

                            chunk_size += 1
                            total_chars += len(next_word) + 1
                            if chunk_size >= 3:
                                break

                    word_chunk = words_data[i : i + chunk_size]
                    start_time = word_chunk[0]["start"]
                    end_time = word_chunk[-1]["end"]

                    words_text = [word["word"].strip() for word in word_chunk]
                    colored_words = self._apply_pos_coloring(words_text)
                    formatted_text = " ".join(colored_words)

                    start = self._format_timestamp(start_time)
                    end = self._format_timestamp(end_time)
                    f.write(
                        f"Dialogue: 0,{start},{end},Dynamic,,0,0,0,,{formatted_text}\n"
                    )
                    i += chunk_size

        self.logger.info(f"ASS saved to {path}")
        return path
