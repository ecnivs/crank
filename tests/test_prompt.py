"""
Tests for prompt.Prompt class.
"""

import pytest
from prompt import Prompt


@pytest.fixture
def prompt_handler(temp_prompt_file, monkeypatch):
    """Create a Prompt instance with test prompt file."""
    # Monkeypatch the default prompt.yml path
    original_init = Prompt.__init__

    def patched_init(self):
        self.prompts = __import__("preset", fromlist=["YmlHandler"]).YmlHandler(
            temp_prompt_file
        )
        self.output_format = {
            "TRANSCRIPT": self.prompts.get("GET_CONTENT", ""),
            "DESCRIPTION": self.prompts.get("GET_DESCRIPTION", ""),
            "SEARCH_TERM": self.prompts.get("GET_SEARCH_TERM", ""),
            "TITLE": self.prompts.get("GET_TITLE", ""),
            "CATEGORY_ID": self.prompts.get("GET_CATEGORY_ID", ""),
        }

    monkeypatch.setattr(Prompt, "__init__", patched_init)
    return Prompt()


class TestPrompt:
    """Test suite for Prompt class."""

    def test_build_includes_topic(self, prompt_handler):
        """Test that build() includes the topic in the prompt."""
        result = prompt_handler.build("test topic", [])
        assert "test topic" in result

    def test_build_includes_used_topics(self, prompt_handler):
        """Test that build() includes used topics to avoid."""
        used = ["topic1", "topic2"]
        result = prompt_handler.build("test", used)
        assert "topic1" in result
        assert "topic2" in result

    def test_build_includes_output_format(self, prompt_handler):
        """Test that build() includes output format instructions."""
        result = prompt_handler.build("test", [])
        assert "TRANSCRIPT" in result
        assert "DESCRIPTION" in result
        assert "SEARCH_TERM" in result
        assert "TITLE" in result
        assert "CATEGORY_ID" in result

    def test_build_includes_selection_note(self, prompt_handler):
        """Test that build() includes transcript selection note."""
        result = prompt_handler.build("test", [])
        assert "candidate transcripts" in result.lower() or "variant" in result.lower()

    def test_empty_used_topics(self, prompt_handler):
        """Test building with empty used topics list."""
        result = prompt_handler.build("test", [])
        assert "test" in result
        assert result.count("TRANSCRIPT") > 0

    def test_multiple_used_topics(self, prompt_handler):
        """Test building with multiple used topics."""
        used = ["topic1", "topic2", "topic3", "topic4"]
        result = prompt_handler.build("new topic", used)
        assert all(topic in result for topic in used)
