"""
Tests for caption.Handler class.
"""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from caption import Handler


class TestCaptionHandler:
    """Test suite for caption.Handler class."""

    @patch("spacy.load")
    @patch("caption.caption.SpeechToText")
    def test_init(self, mock_stt_class, mock_spacy_load, temp_dir):
        """Test Handler initialization."""
        mock_stt = MagicMock()
        mock_stt_class.return_value = mock_stt
        mock_nlp = MagicMock()
        mock_spacy_load.return_value = mock_nlp

        handler = Handler(workspace=temp_dir, model_size="tiny", font="Arial")
        assert handler.workspace == Path(temp_dir)
        assert handler.font == "Arial"
        assert handler.stt == mock_stt

    @patch("spacy.load")
    @patch("caption.caption.SpeechToText")
    def test_format_timestamp(self, mock_stt_class, mock_spacy_load, temp_dir):
        """Test timestamp formatting."""
        mock_stt_class.return_value = MagicMock()
        mock_spacy_load.return_value = MagicMock()

        handler = Handler(workspace=temp_dir, model_size="tiny", font="Arial")

        # Test various timestamps
        assert handler._format_timestamp(0.0) == "0:00:00.00"
        assert handler._format_timestamp(65.5) == "0:01:05.50"
        assert handler._format_timestamp(3661.25) == "1:01:01.25"

    @patch("spacy.load")
    @patch("caption.caption.SpeechToText")
    def test_get_captions_success(
        self, mock_stt_class, mock_spacy_load, temp_dir, sample_audio_file
    ):
        """Test successful caption generation."""
        mock_stt = MagicMock()
        mock_stt.transcribe.return_value = {
            "text": "Test transcript",
            "segments": [
                {
                    "start": 0.0,
                    "end": 5.0,
                    "text": "Test transcript",
                    "words": [
                        {"word": "Test", "start": 0.0, "end": 2.0},
                        {"word": "transcript", "start": 2.0, "end": 5.0},
                    ],
                }
            ],
        }
        mock_stt_class.return_value = mock_stt

        mock_nlp = MagicMock()

        class MockToken:
            def __init__(self, text, pos_):
                self.text = text
                self.pos_ = pos_

        class MockDoc:
            def __init__(self):
                self.text = "Test transcript"
                self.tokens = [
                    MockToken("Test", "NOUN"),
                    MockToken("transcript", "NOUN"),
                ]

            def __iter__(self):
                return iter(self.tokens)

        mock_nlp.return_value = MockDoc()
        mock_spacy_load.return_value = mock_nlp

        handler = Handler(workspace=temp_dir, model_size="tiny", font="Arial")
        result = handler.get_captions(sample_audio_file)

        assert result.exists()
        assert result.suffix == ".ass"
        assert "Dialogue" in result.read_text()

    @patch("spacy.load")
    @patch("caption.caption.SpeechToText")
    def test_get_captions_missing_audio(
        self, mock_stt_class, mock_spacy_load, temp_dir
    ):
        """Test caption generation with missing audio file."""
        mock_stt_class.return_value = MagicMock()
        mock_spacy_load.return_value = MagicMock()

        handler = Handler(workspace=temp_dir, model_size="tiny", font="Arial")
        fake_audio = temp_dir / "missing.wav"

        with pytest.raises(FileNotFoundError, match="Audio file not found"):
            handler.get_captions(fake_audio)

    @patch("spacy.load")
    @patch("caption.caption.SpeechToText")
    def test_get_captions_no_words(
        self, mock_stt_class, mock_spacy_load, temp_dir, sample_audio_file
    ):
        """Test caption generation with segments but no words."""
        mock_stt = MagicMock()
        mock_stt.transcribe.return_value = {
            "text": "Test transcript",
            "segments": [
                {
                    "start": 0.0,
                    "end": 5.0,
                    "text": "Test transcript",
                    "words": [],
                }
            ],
        }
        mock_stt_class.return_value = mock_stt
        mock_spacy_load.return_value = MagicMock()

        handler = Handler(workspace=temp_dir, model_size="tiny", font="Arial")
        result = handler.get_captions(sample_audio_file)

        assert result.exists()
        content = result.read_text()
        assert "Test transcript" in content

    @patch("spacy.load")
    @patch("caption.caption.SpeechToText")
    def test_apply_pos_coloring(self, mock_stt_class, mock_spacy_load, temp_dir):
        """Test part-of-speech coloring."""
        mock_stt_class.return_value = MagicMock()

        mock_nlp = MagicMock()

        class MockToken:
            def __init__(self, text, pos_):
                self.text = text
                self.pos_ = pos_

        class MockDoc:
            def __init__(self):
                self.tokens = [
                    MockToken("run", "VERB"),
                    MockToken("it", "PRON"),
                    MockToken("fast", "ADJ"),
                ]

            def __iter__(self):
                return iter(self.tokens)

        mock_nlp.return_value = MockDoc()
        mock_spacy_load.return_value = mock_nlp

        handler = Handler(workspace=temp_dir, model_size="tiny", font="Arial")
        words = ["run", "it", "fast"]
        colored = handler._apply_pos_coloring(words)

        # VERB should be colored
        assert any("\\c&HD8BFD8&" in str(w) for w in colored)
        # PRON should be colored
        assert any("\\c&FFDAB9&" in str(w) for w in colored)
