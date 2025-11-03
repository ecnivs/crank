"""
Tests for preset.YmlHandler class.
"""

import yaml
from preset import YmlHandler


class TestYmlHandler:
    """Test suite for YmlHandler."""

    def test_init_with_existing_file(self, temp_dir):
        """Test initializing YmlHandler with an existing file."""
        preset_path = temp_dir / "test_preset.yml"
        data = {"NAME": "test", "VALUE": 42}
        with preset_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(data, f)

        handler = YmlHandler(preset_path)
        assert handler.path == preset_path
        assert handler.get("NAME") == "test"
        assert handler.get("VALUE") == 42

    def test_init_with_nonexistent_file(self, temp_dir):
        """Test initializing YmlHandler with a non-existent file."""
        preset_path = temp_dir / "nonexistent.yml"
        handler = YmlHandler(preset_path)
        assert handler.path == preset_path
        assert handler.get("NAME") is None
        assert handler.state == {}

    def test_get_with_default(self, preset_handler):
        """Test getting a value with a default."""
        assert preset_handler.get("NONEXISTENT", "default") == "default"
        assert preset_handler.get("NAME", "default") == "test_channel"

    def test_get_without_default(self, preset_handler):
        """Test getting a value without default."""
        assert preset_handler.get("NAME") == "test_channel"
        assert preset_handler.get("NONEXISTENT") is None

    def test_set_value(self, preset_handler, temp_preset_file):
        """Test setting a value."""
        preset_handler.set("NEW_KEY", "new_value")
        assert preset_handler.get("NEW_KEY") == "new_value"

        # Verify it's persisted to file
        handler2 = YmlHandler(temp_preset_file)
        assert handler2.get("NEW_KEY") == "new_value"

    def test_delete_key(self, preset_handler, temp_preset_file):
        """Test deleting a key."""
        preset_handler.set("TO_DELETE", "value")
        assert preset_handler.get("TO_DELETE") == "value"

        preset_handler.delete("TO_DELETE")
        assert preset_handler.get("TO_DELETE") is None

        # Verify it's persisted
        handler2 = YmlHandler(temp_preset_file)
        assert handler2.get("TO_DELETE") is None

    def test_update_multiple_keys(self, preset_handler, temp_preset_file):
        """Test updating multiple keys at once."""
        preset_handler.update({"KEY1": "value1", "KEY2": "value2"})
        assert preset_handler.get("KEY1") == "value1"
        assert preset_handler.get("KEY2") == "value2"

        # Verify persistence
        handler2 = YmlHandler(temp_preset_file)
        assert handler2.get("KEY1") == "value1"
        assert handler2.get("KEY2") == "value2"

    def test_preserves_existing_keys(self, preset_handler):
        """Test that set doesn't affect other keys."""
        original_name = preset_handler.get("NAME")
        preset_handler.set("NEW_KEY", "value")
        assert preset_handler.get("NAME") == original_name

    def test_handles_complex_data(self, preset_handler):
        """Test handling complex data structures."""
        complex_data = {
            "list": [1, 2, 3],
            "nested": {"key": "value"},
            "mixed": ["a", {"b": "c"}],
        }
        preset_handler.set("COMPLEX", complex_data)
        result = preset_handler.get("COMPLEX")
        assert result == complex_data
