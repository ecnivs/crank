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
4. **Plugin** receives complete pipeline data and returns a video path

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
from typing import Any, Dict

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
        # Initialize your plugin-specific resources here

    def _load_config(self) -> Dict[str, Any]:
        """Load plugin configuration from config.yml.

        Returns:
            Dictionary containing plugin configuration.
        """
        config_file = Path(__file__).parent / "config.yml"
        if config_file.exists():
            try:
                with config_file.open("r", encoding="utf-8") as f:
                    config = yaml.safe_load(f) or {}
                    self.logger.info(f"Loaded config from {config_file}")
                    return config
            except Exception as e:
                self.logger.warning(
                    f"Failed to load config from {config_file}: {e}. Using defaults."
                )
        return {}

    def get_media(self, data: Dict[str, Any]) -> Path:
        """Generate and return path to background video.

        Args:
            data: Dictionary containing ALL available pipeline data:
                  - transcript: Generated transcript text
                  - title: Video title
                  - description: Video description
                  - search_term: Search term for video content
                  - categoryId: YouTube category ID
                  Extract only the fields you need.

        Returns:
            Path: Path to processed background video file.
        """
        # Extract the data you need
        title = data.get("title", "")
        transcript = data.get("transcript", "")
        
        # Your custom video generation logic here
        # ...
        
        # Return path to generated video
        video_path = self.workspace / "background_video.mp4"
        return video_path
```

### Step 3: Create config.yml (Optional)

Create `plugins/your_plugin_name/config.yml`:

```yaml
# Your plugin configuration
api_key: your_api_key_here
max_results: 10
custom_setting: value
```

### Step 4: Plugin Class Requirements

- **Class name**: Must end with `Plugin` (e.g., `MyCustomPlugin`)
- **Inheritance**: Must inherit from `BackgroundVideoPlugin`
- **Initialization**: Must accept `workspace: Path` parameter
- **Method**: Must implement `get_media(data: Dict[str, Any]) -> Path`

## Plugin Interface

### BackgroundVideoPlugin Base Class

```python
class BackgroundVideoPlugin(ABC):
    def __init__(self, workspace: Path) -> None:
        """Initialize with workspace directory."""
        self.workspace: Path = workspace

    @abstractmethod
    def get_media(self, data: Dict[str, Any]) -> Path:
        """Generate and return path to background video."""
        pass
```

### Data Dictionary

The `data` dictionary passed to `get_media()` contains all available pipeline information:

```python
data = {
    "transcript": "Say hello: Welcome to our channel...",
    "title": "Amazing Facts About Space",
    "description": "Learn about space exploration...",
    "search_term": "space exploration cinematic",
    "categoryId": "24"
}
```

**Important**: 
- Plugins can use ANY combination of these fields
- Plugins can ignore fields they don't need
- The app passes everything available - plugins decide what to use

## Example Plugins

### Example 1: Using search_term (Default Plugin)

```python
class DefaultPlugin(BackgroundVideoPlugin):
    def get_media(self, data: Dict[str, Any]) -> Path:
        search_term = data.get("search_term", "")
        # Use search_term for YouTube scraping
        return self.scraper.get_media(search_term)
```

### Example 2: Using transcript for AI-generated visuals

```python
class AIVisualsPlugin(BackgroundVideoPlugin):
    def get_media(self, data: Dict[str, Any]) -> Path:
        transcript = data.get("transcript", "")
        # Generate visuals from transcript using AI
        return self._generate_ai_visuals(transcript)
```

### Example 3: Using title and description

```python
class KeywordPlugin(BackgroundVideoPlugin):
    def get_media(self, data: Dict[str, Any]) -> Path:
        title = data.get("title", "")
        description = data.get("description", "")
        # Use title + description for keyword-based selection
        keywords = self._extract_keywords(title, description)
        return self._select_video_by_keywords(keywords)
```

### Example 4: Using all fields

```python
class MultiSourcePlugin(BackgroundVideoPlugin):
    def get_media(self, data: Dict[str, Any]) -> Path:
        # Use all available data for complex generation
        transcript = data.get("transcript", "")
        title = data.get("title", "")
        search_term = data.get("search_term", "")
        category = data.get("categoryId", "")
        
        # Complex multi-source logic
        return self._generate_from_multiple_sources(
            transcript, title, search_term, category
        )
```

## Configuration

### Plugin Configuration

Each plugin loads its own configuration from `plugins/{plugin_name}/config.yml`:

```yaml
# plugins/my_plugin/config.yml
api_key: your_api_key
max_results: 10
quality: high
```

Access configuration in your plugin:

```python
def __init__(self, workspace: Path) -> None:
    super().__init__(workspace)
    self.config = self._load_config()
    api_key = self.config.get("api_key")
```

### Preset Configuration

In `preset.yml`, only specify which plugin to use:

```yaml
# config/preset.yml
BACKGROUND_PLUGIN: my_custom_plugin  # Optional, defaults to "default"
```

**Important**: Plugin-specific settings belong in the plugin's `config.yml`, not in `preset.yml`.

## Plugin Discovery

The plugin registry automatically discovers plugins by:

1. Scanning `plugins/` directory for subdirectories
2. Looking for `plugin.py` in each subdirectory
3. Finding a class ending with `Plugin` that inherits from `BackgroundVideoPlugin`
4. Registering the plugin with the directory name as the plugin identifier

### Discovery Rules

- Plugin directory name = plugin identifier
- Must have `plugin.py` file
- Plugin class name must end with `Plugin`
- Plugin class must inherit from `BackgroundVideoPlugin`

## Error Handling

### Plugin Loading Errors

If a plugin fails to load:
- The registry logs an error
- The app falls back to the "default" plugin
- Clear error messages are logged

### Plugin Execution Errors

Handle errors in your plugin:

```python
def get_media(self, data: Dict[str, Any]) -> Path:
    try:
        # Your logic
        return video_path
    except Exception as e:
        self.logger.error(f"Failed to generate video: {e}", exc_info=True)
        raise  # Re-raise to let orchestrator handle it
```

## Best Practices

### 1. Self-Contained Plugins

- Keep all plugin code and resources in the plugin directory
- Load configuration from plugin's own `config.yml`
- Don't depend on external files outside the plugin directory

### 2. Logging

Use the logger for debugging and monitoring:

```python
self.logger.debug("Processing video generation")
self.logger.info("Video generated successfully")
self.logger.warning("Using fallback method")
self.logger.error("Failed to generate video", exc_info=True)
```

### 3. Workspace Management

- Use `self.workspace` for temporary files
- Clean up temporary files when done
- Return paths relative to workspace or absolute paths

### 4. Configuration Validation

Validate configuration in `__init__`:

```python
def __init__(self, workspace: Path) -> None:
    super().__init__(workspace)
    self.config = self._load_config()
    
    # Validate required config
    if "api_key" not in self.config:
        raise ValueError("api_key is required in config.yml")
```

### 5. Data Extraction

Extract only what you need:

```python
def get_media(self, data: Dict[str, Any]) -> Path:
    # Extract only needed fields
    title = data.get("title", "")
    transcript = data.get("transcript", "")
    
    # Ignore fields you don't use
    # The app doesn't care what you use
```

### 6. Type Hints

Use proper type hints:

```python
from typing import Any, Dict
from pathlib import Path

def get_media(self, data: Dict[str, Any]) -> Path:
    """Type hints help with IDE support and documentation."""
    pass
```

## Testing

### Manual Testing

1. Create your plugin in `plugins/your_plugin/`
2. Add `BACKGROUND_PLUGIN: your_plugin` to `preset.yml`
3. Run the application
4. Check logs for plugin loading and execution

### Unit Testing

Test your plugin independently:

```python
from pathlib import Path
from plugins.your_plugin.plugin import YourPluginPlugin

def test_plugin():
    workspace = Path("/tmp/test_workspace")
    plugin = YourPluginPlugin(workspace)
    
    data = {
        "title": "Test Title",
        "transcript": "Test transcript",
        "search_term": "test",
    }
    
    video_path = plugin.get_media(data)
    assert video_path.exists()
```

## Troubleshooting

### Plugin Not Found

**Error**: `Plugin 'your_plugin' not found`

**Solutions**:
- Check plugin directory exists: `plugins/your_plugin/`
- Check `plugin.py` exists: `plugins/your_plugin/plugin.py`
- Check class name ends with `Plugin`
- Check class inherits from `BackgroundVideoPlugin`

### Plugin Not Loading

**Error**: `Failed to load plugin from plugins/your_plugin/plugin.py`

**Solutions**:
- Check for syntax errors in `plugin.py`
- Check imports are correct
- Check class is properly defined
- Review logs for detailed error messages

### Configuration Not Loading

**Error**: Config not found or invalid

**Solutions**:
- Check `config.yml` exists in plugin directory
- Check YAML syntax is valid
- Check file permissions
- Plugin will use empty dict if config missing

## Advanced Topics

### Plugin Dependencies

If your plugin needs external dependencies:

1. Document them in a `requirements.txt` in your plugin directory
2. Users install them separately
3. Import them in your plugin code

### Plugin Resources

Store plugin-specific resources in your plugin directory:

```
plugins/my_plugin/
├── plugin.py
├── config.yml
├── assets/
│   └── templates/
└── models/
    └── model.pkl
```

Access them using `Path(__file__).parent`:

```python
assets_dir = Path(__file__).parent / "assets"
template_path = assets_dir / "templates" / "template.json"
```

### Multiple Plugin Versions

To support multiple versions:

```
plugins/
├── my_plugin_v1/
│   └── plugin.py
└── my_plugin_v2/
    └── plugin.py
```

Users specify version in `preset.yml`:

```yaml
BACKGROUND_PLUGIN: my_plugin_v2
```

## Summary

- **Create**: `plugins/{name}/plugin.py` with a class ending in `Plugin`
- **Inherit**: From `BackgroundVideoPlugin`
- **Implement**: `get_media(data: Dict[str, Any]) -> Path`
- **Configure**: Use `plugins/{name}/config.yml` for settings
- **Use**: Any data from the pipeline dictionary
- **Return**: Path to generated background video

Plugins are powerful, flexible, and completely independent. Create plugins that use any data and any generation strategy without modifying the core application!
