"""
Pytest configuration and shared fixtures.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

from src.preset import YmlHandler


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_preset_file(temp_dir):
    """Create a temporary preset.yml file."""
    preset_path = temp_dir / "preset.yml"
    preset_data = {
        "NAME": "test_channel",
        "PROMPT": None,
        "UPLOAD": False,
        "DELAY": 2.5,
        "WHISPER_MODEL": "tiny",
        "FONT": "Arial",
        "GEMINI_API_KEY": "test_api_key_12345",
    }
    with preset_path.open("w", encoding="utf-8") as f:
        import yaml

        yaml.safe_dump(preset_data, f)
    return preset_path


@pytest.fixture
def temp_prompt_file(temp_dir):
    """Create a temporary prompt.yml file."""
    prompt_path = temp_dir / "prompt.yml"
    prompt_data = {
        "GET_CONTENT": "Generate content about: {topic}",
        "GET_TITLE": "Create a title for: {content}",
        "GET_SEARCH_TERM": "Search term: {content}",
        "GET_DESCRIPTION": "Description: {content}",
        "GET_CATEGORY_ID": "Category ID: 24",
    }
    with prompt_path.open("w", encoding="utf-8") as f:
        import yaml

        yaml.safe_dump(prompt_data, f)
    return prompt_path


@pytest.fixture
def preset_handler(temp_preset_file):
    """Create a YmlHandler instance with test preset."""
    return YmlHandler(temp_preset_file)


@pytest.fixture
def mock_gemini_client():
    """Create a mock Gemini client."""
    client = MagicMock()

    mock_response = MagicMock()
    mock_response.text = "TRANSCRIPT: Say excitedly: Test transcript\nTITLE: Test Title\nDESCRIPTION: Test Description\nSEARCH_TERM: test search\nCATEGORY_ID: 24"
    mock_candidate = MagicMock()
    mock_candidate.content.text = mock_response.text
    mock_response.candidates = [mock_candidate]

    client.models.generate_content.return_value = mock_response

    mock_audio_response = MagicMock()
    mock_audio_part = MagicMock()
    mock_audio_part.inline_data.data = b"fake_audio_data" * 100
    mock_audio_candidate = MagicMock()
    mock_audio_candidate.content.parts = [mock_audio_part]
    mock_audio_response.candidates = [mock_audio_candidate]

    def generate_content_side_effect(model, contents, config=None):
        if config and "AUDIO" in str(config.response_modalities):
            return mock_audio_response
        return mock_response

    client.models.generate_content.side_effect = generate_content_side_effect

    return client


@pytest.fixture
def mock_ffmpeg_probe(monkeypatch):
    """Mock ffprobe subprocess calls."""

    def mock_check_output(cmd, **kwargs):
        if "ffprobe" in cmd:
            return json.dumps({"format": {"duration": "30.5"}}).encode()
        return b""

    import subprocess

    monkeypatch.setattr(subprocess, "check_output", mock_check_output)
    monkeypatch.setattr(subprocess, "run", Mock(return_value=Mock(returncode=0)))


@pytest.fixture
def mock_ffmpeg_success(monkeypatch):
    """Mock successful FFmpeg subprocess calls."""

    def mock_run(cmd, **kwargs):
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.check_returncode = Mock()
        return mock_result

    import subprocess

    monkeypatch.setattr(subprocess, "run", mock_run)


@pytest.fixture
def mock_file_exists(monkeypatch):
    """Mock Path.exists() to return True for test files."""
    original_exists = Path.exists

    def exists(self):
        if isinstance(self, Path):
            # Allow specific test files
            if any(
                x in str(self)
                for x in [".ass", ".wav", ".mp4", "preset.yml", "prompt.yml"]
            ):
                return True
        return original_exists(self)

    monkeypatch.setattr(Path, "exists", exists)


@pytest.fixture
def mock_youtube_service():
    """Create a mock YouTube API service."""
    service = MagicMock()
    mock_insert = MagicMock()
    mock_request = MagicMock()
    mock_request.execute.return_value = {"id": "test_video_id_123"}
    mock_insert.return_value = mock_request
    service.videos.return_value = MagicMock(insert=mock_insert)
    return service


@pytest.fixture
def sample_transcript():
    """Sample transcript text."""
    return "Say excitedly: This is a test transcript for YouTube Shorts generation."


@pytest.fixture
def sample_gemini_response():
    """Sample Gemini API response."""
    return """TRANSCRIPT: Say excitedly: This is a test transcript.
TITLE: Test Video Title
DESCRIPTION: This is a test description with hashtags.
SEARCH_TERM: test visual content
CATEGORY_ID: 24"""


@pytest.fixture
def sample_audio_file(temp_dir):
    """Create a sample audio file."""
    audio_path = temp_dir / "test_audio.wav"
    audio_path.write_bytes(b"fake_wav_data" * 100)
    return audio_path


@pytest.fixture
def sample_video_file(temp_dir):
    """Create a sample video file."""
    video_path = temp_dir / "test_video.mp4"
    video_path.write_bytes(b"fake_mp4_data" * 1000)
    return video_path


@pytest.fixture
def sample_ass_file(temp_dir):
    """Create a sample ASS subtitle file."""
    ass_path = temp_dir / "test_captions.ass"
    ass_content = """[Script Info]
ScriptType: v4.00+
[Events]
Dialogue: 0,0:00:00.00,0:00:05.00,Dynamic,,0,0,0,,Test subtitle
"""
    ass_path.write_text(ass_content, encoding="utf-8")
    return ass_path


@pytest.fixture(autouse=True)
def reset_environment(monkeypatch):
    """Reset environment variables before each test."""
    # Remove API keys from environment
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("PRESET_PATH", raising=False)
    yield
    # Cleanup after test


@pytest.fixture
def mock_whisper_model():
    """Mock Whisper model for transcription."""
    mock_model = MagicMock()

    class MockSegment:
        def __init__(self):
            self.start = 0.0
            self.end = 5.0
            self.text = "Test transcript"
            self.words = [
                Mock(word="Test", start=0.0, end=1.0),
                Mock(word="transcript", start=1.0, end=2.0),
            ]

    class MockInfo:
        language = "en"
        duration = 5.0

    mock_segments = [MockSegment()]
    mock_info = MockInfo()
    mock_model.transcribe.return_value = (mock_segments, mock_info)
    return mock_model


@pytest.fixture
def mock_spacy_model():
    """Mock SpaCy model for NLP processing."""
    mock_model = MagicMock()

    class MockToken:
        def __init__(self, text, pos_):
            self.text = text
            self.pos_ = pos_

    class MockDoc:
        def __init__(self, text):
            self.text = text

    def load_side_effect(name, **kwargs):
        mock_nlp = MagicMock()
        mock_nlp.return_value = MockDoc("test text")
        return mock_nlp

    import spacy
    from unittest.mock import patch

    with patch("spacy.load", side_effect=load_side_effect):
        yield mock_model
