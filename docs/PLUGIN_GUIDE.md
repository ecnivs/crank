# Plugin Development Guide

## Overview

The Crank plugin system allows you to create custom background video generators that integrate seamlessly with the video generation pipeline. Plugins are completely self-contained and can use any data from the pipeline to generate background videos.

## Architecture

### Plugin System Flow

```
User Input → Core → Plugin Registry → Plugin Instance → Background Video
```

1. **Core** loads the plugin name from `preset.yml` (defaults to "default")
2. **Plugin Registry** discovers and loads plugins from the `plugins/` directory
3. **Plugin Instance** is created with a workspace directory
4. **Plugin** receives complete pipeline data (including audio/captions) and returns a video path (and optional config)

### Key Principles

- **Self-contained**: Each plugin has its own directory with code and config
- **Independent**: Plugins can use any data they need from the pipeline
- **Zero coupling**: The app has no knowledge of plugin internals
- **Flexible**: Plugins can implement any video generation strategy

## Plugin Structure

Each plugin must be in its own directory under `plugins/`:

```
plugins/
└── your_plugin/
    ├── plugin.py          # Required: Plugin implementation
    └── config.yml         # Optional: Plugin configuration
```

### Directory Naming

- Plugin directory name becomes the plugin identifier
- Use lowercase with underscores (e.g., `my_custom_plugin`)
- Directory name must match the plugin name used in `preset.yml`

## Creating a Plugin

### Step 1: Create Plugin Directory

```bash
mkdir -p plugins/your_plugin_name
```

### Step 2: Create plugin.py

Create `plugins/your_plugin_name/plugin.py`:

```python
"""Your custom background video plugin."""

import logging
import yaml
from pathlib import Path
from typing import Any, Dict, Union

from src.plugins.base import BackgroundVideoPlugin


class YourPluginNamePlugin(BackgroundVideoPlugin):
    """Your plugin description."""

    def __init__(self, workspace: Path) -> None:
        """Initialize the plugin.

        Args:
            workspace: Directory for temporary files and plugin workspace.
        """
        super().__init__(workspace)
        self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)
        self.config: Dict[str, Any] = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load plugin configuration from config.yml."""
        config_file = Path(__file__).parent / "config.yml"
        if config_file.exists():
            try:
                with config_file.open("r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                self.logger.warning(f"Failed to load config: {e}")
        return {}

    def get_prompt_context(self, topic: str) -> str:
        """Inject instructions into the Gemini prompt."""
        # Optional: Force the AI to write in a specific style
        return "Write the script in a mysterious, dark tone."

    def get_media(self, data: Dict[str, Any]) -> Union[Path, Dict[str, Any]]:
        """Generate and return path to background video."""

        # 1. Access available data
        transcript = data.get("transcript", "")
        caption_data = data.get("caption_data", {}) # Word-level timestamps!
        audio_path = Path(data.get("audio_path", "")) 

        # 2. Your generation logic
        video_path = self.workspace / "background.mp4"
        # ... generate video at video_path ...

        # 3. Return simple path OR advanced dict
        # Simple: return video_path

        # Advanced: Control the pipeline
        return {
            "video_path": video_path,
            "audio_path": self.workspace / "spooky_music.mp3", # Mix this audio!
            "config": {
                "suppress_captions": True # Don't burn standard subtitles (I'll do it myself!)
            }
        }
```

### Step 3: Create config.yml (Optional)

Create `plugins/your_plugin_name/config.yml`:

```yaml
# Your plugin configuration
api_key: your_api_key_here
style: cinematic
```

## Plugin Interface

### 1. The `get_media` Method

This is the core method. It receives `data` and returns the video result.

#### Input: `data` Dictionary
The `data` dictionary contains EVERYTHING generated during the pipeline:

```python
data = {
    # Text Data
    "transcript": "Say hello: Welcome to our channel...",
    "title": "Amazing Facts About Space",
    "description": "Learn about space...",
    "search_term": "space exploration cinematic",
    "categoryId": "24",
    
    # Asset Paths
    "audio_path": "/tmp/.../speech.wav",
    "captions_path": "/tmp/.../captions.ass",
    
    # Rich Data
    "caption_data": {
        "text": "...",
        "segments": [
            {
                "start": 0.0,
                "end": 2.5,
                "text": "Welcome to...",
                "words": [
                    {"word": "Welcome", "start": 0.0, "end": 0.5},
                    ...
                ]
            }
        ]
    }
}
```

#### Output: Video Result
You can return one of two things:

**Option A: Simple Path** (Backward Compatible)
```python
return Path("/path/to/video.mp4")
```
*Effect*: The app uses this video, mixes it with the voiceover, and burns standard subtitles on top.

**Option B: Advanced Dictionary** (For "Power" Plugins)
```python
return {
    "video_path": Path("/path/to/video.mp4"),       # Required
    "audio_path": Path("/path/to/background.mp3"),  # Optional: Mixed with voiceover
    "config": {
        "suppress_captions": True                   # Optional: Disable standard subtitles
    }
}
```

### 2. The `get_prompt_context` Method

**Optional**. Implement this to give instructions to the LLM *before* script generation.

```python
def get_prompt_context(self, topic: str) -> str:
    return "Ensure the script uses short, punchy sentences suitable for a montage."
```

## Advanced Features Guide

### Feature A: Kinetic Typography / Custom Subtitles
If your plugin renders text directly onto the video (like a lyric video or Kinetic Typography), you don't want the standard `.ass` subtitles printed on top.

1. Implement your text rendering using `caption_data` (timestamps) inside `get_media`.
2. Return with suppression:
   ```python
   return {
       "video_path": video,
       "config": {"suppress_captions": True}
   }
   ```

### Feature B: Audio Ambience
If your plugin generates a scary story, you might want rain sounds or creepy music.

1. Generate or download the audio file in `get_media`.
2. Return it:
   ```python
   return {
       "video_path": video,
       "audio_path": "/path/to/rain_sounds.mp3"
   }
   ```
   The editor will automatically use `amix` to combine the Voiceover + Your Audio.

### Feature C: Prompt Injection (Persona)
If you want to create a "Roast" plugin where the AI mocks the topic.

1. Implementation:
   ```python
   def get_prompt_context(self, topic: str) -> str:
       return "Write the script as a roast. Be sarcastic and funny."
   ```

## Example Plugins

### Example 1: The "Simple Scraper"
Just finds a video based on the search term.

```python
class SimplePlugin(BackgroundVideoPlugin):
    def get_media(self, data: Dict[str, Any]) -> Path:
        term = data.get("search_term")
        return self.scraper.download(term)
```

### Example 2: The "Kinetic Type" Generator
Uses timestamps to animate text and disables standard captions.

```python
class KineticPlugin(BackgroundVideoPlugin):
    def get_media(self, data: Dict[str, Any]) -> Union[Path, Dict[str, Any]]:
        captions = data.get("caption_data")
        # ... generate animated text video using captions ...
        return {
            "video_path": generated_video,
            "config": {"suppress_captions": True}
        }
```

## Troubleshooting

- **Plugin Not Found**: Check directory name matches `preset.yml`.
- **Missing Data**: Ensure you check if keys exist (e.g., `data.get("audio_path")`) as some might be missing in partial runs (though usually present).
- **FFmpeg Errors**: If mixing audio, ensure your audio file is valid.

## Summary

- **Create**: `plugins/{name}/plugin.py` with a class ending in `Plugin`
- **Inherit**: From `BackgroundVideoPlugin`
- **Inject**: Use `get_prompt_context` to guide the AI.
- **Implement**: `get_media` to generate video.
- **Control**: Return a Dict to mix audio or suppress captions.
