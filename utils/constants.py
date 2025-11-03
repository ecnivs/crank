"""
Application-wide constants.
"""
from pathlib import Path

# Video dimensions for YouTube Shorts
SHORT_WIDTH = 1080
SHORT_HEIGHT = 1920
SHORT_ASPECT_RATIO = 9 / 16

# Video duration limits (in seconds)
MAX_VIDEO_DURATION = 60.0
MIN_VIDEO_DURATION = 1.0
TARGET_VIDEO_DURATION = 60.0

# Subtitle configuration
SUBTITLE_RESOLUTION_X = 1920
SUBTITLE_RESOLUTION_Y = 1080
SUBTITLE_FONT_SIZE = 48
DEFAULT_FONT = "Comic Sans MS"

# Rate limiting
RATE_LIMIT_COOLDOWN_HOURS = 24
RATE_LIMIT_CHECK_INTERVAL_SECONDS = 1

# Cookie refresh interval (in seconds)
COOKIE_REFRESH_INTERVAL = 3600  # 1 hour

# Default upload delay (in hours)
DEFAULT_UPLOAD_DELAY = 2.5

# File paths
DEFAULT_SECRETS_FILE = Path("secrets.json")
DEFAULT_PRESET_FILE = Path("preset.yml")
DEFAULT_PROMPT_FILE = Path("prompt.yml")
DEFAULT_LOG_FILE = Path("crank.log")
TOKEN_FOLDER = Path(".tokens")

# Gemini API
DEFAULT_GEMINI_MODEL = "2.5"
GEMINI_MODELS = {
    "2.5": "gemini-2.5-flash",
    "2.0": "gemini-2.0-flash",
}
DEFAULT_VOICE = "Alnilam"

# Whisper model
DEFAULT_WHISPER_MODEL = "small"

# Video processing
SCENE_THRESHOLD = 0.35
MAX_SEGMENT_LENGTH = 7.0
TEXT_DETECTION_THRESHOLD = 22.0

# YouTube download
MAX_SEARCH_RESULTS = 10
MAX_DOWNLOAD_RETRIES = 4

# FFmpeg settings
FFMPEG_PRESET = "medium"
FFMPEG_CRF = 23
FFMPEG_AUDIO_BITRATE = "128k"
FFMPEG_AUDIO_CODEC = "aac"
FFMPEG_VIDEO_CODEC = "libx264"
FFMPEG_PIX_FMT = "yuv420p"

