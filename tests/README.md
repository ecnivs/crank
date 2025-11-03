# Test Suite

This directory contains comprehensive tests for the Crank project.

## Running Tests

### Prerequisites
**Important:** You need to install the project dependencies first before running tests:

```bash
# Install all dependencies (including test dependencies)
uv sync --extra dev

# OR install just the project dependencies if you want to run tests later
uv sync
```

### Run all tests
```bash
pytest
```

### Run with coverage
```bash
pytest --cov=. --cov-report=html
```

### Run specific test files
```bash
pytest tests/test_yml_handler.py
pytest tests/test_gemini.py
```

### Run specific test classes or functions
```bash
pytest tests/test_yml_handler.py::TestYmlHandler::test_set_value
```

### Run tests by marker
```bash
pytest -m unit          # Run only unit tests
pytest -m integration   # Run only integration tests
pytest -m "not slow"    # Skip slow tests
```

## Test Structure

- `conftest.py` - Shared fixtures and test configuration
- `test_yml_handler.py` - Tests for preset YAML handler
- `test_prompt.py` - Tests for prompt builder
- `test_gemini.py` - Tests for Gemini API client
- `test_editor.py` - Tests for video editor (FFmpeg operations)
- `test_uploader.py` - Tests for YouTube uploader
- `test_caption.py` - Tests for caption/subtitle handler
- `test_orchestrator.py` - Integration tests for the orchestrator pipeline
- `test_main.py` - Tests for main application logic
- `test_main_cli.py` - Tests for CLI argument parsing

## Test Coverage

The test suite aims for high coverage of:
- ✅ Configuration management (YmlHandler)
- ✅ Prompt building
- ✅ API interactions (Gemini, YouTube)
- ✅ Video processing (Editor)
- ✅ Caption generation
- ✅ Error handling
- ✅ CLI argument parsing
- ✅ Environment variable handling

## Mocking Strategy

- External APIs (Gemini, YouTube) are mocked
- FFmpeg subprocess calls are mocked
- File system operations use temporary directories
- External dependencies (Whisper, SpaCy) are mocked

## Notes

- Tests use temporary directories for file operations
- Async tests use pytest-asyncio
- Environment variables are reset between tests
- All external dependencies are mocked to avoid network calls

