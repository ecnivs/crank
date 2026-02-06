<div align="center">

<img width="1452" height="352" alt="crank" src="https://github.com/user-attachments/assets/bda075e8-8cb2-42c8-9e8b-6c7faa205774" />


</div>

<p align="center">
  <a href="https://github.com/ecnivs/crank/stargazers">
    <img src="https://img.shields.io/github/stars/ecnivs/crank?style=flat-square">
  </a>
  <a href="https://github.com/ecnivs/crank/issues">
    <img src="https://img.shields.io/github/issues/ecnivs/crank?style=flat-square">
  </a>
  <a href="https://github.com/ecnivs/crank/blob/master/LICENSE">
    <img src="https://img.shields.io/badge/license-Custom-blue?style=flat-square">
  </a>
  <img src="https://img.shields.io/github/languages/top/ecnivs/crank?style=flat-square">
  <img src="https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-informational?style=flat-square">
</p>

## Overview
**Crank** takes a topic and generates a complete YouTube Short, including video and metadata, ready for upload. Designed for fast, efficient content creation with full control over the output.

## 🛠️ Prerequisites
- Python 3.x (Tested with Python 3.13)
- `uv` (Python package manager)
- `ffmpeg` and `ffprobe` installed and available in your system PATH (required for video processing)

#### Environment Variables
**Crank** uses a `.env` file to load sensitive keys and config values.
Make sure to create a `.env` file in the root directory containing your API keys, for example:
```ini
GEMINI_API_KEY=your_api_key_here
```

#### Credential Files
The other credentials are stored as JSON files inside the root directory:
- `secrets.json` — OAuth 2.0 client credentials JSON used for YouTube API upload authentication

## ⚙️ Customization
**Crank** is fully configurable. You can adjust prompts, upload behavior, and other settings using your preferred method.

#### Default settings in `config/preset.yml`
Change the following directly in the file:
- `NAME`: The channel name
- `PROMPT`: Topic or idea to base the generated video on
- `UPLOAD`: `true` or `false` to enable/disable uploads
- `DELAY`: Number of hours between uploads: `0` for instant upload, or any positive number to schedule the video that many hours later (defaults to `2.5`)
- `GEMINI_API_KEY`: Optional channel-specific API key (overrides .env if set)
- `WHISPER_MODEL`: Preferred whisper model (`tiny`, `base`, `small`, `medium`, `large-v1`, `large-v2`, `large-v3`; defaults to `small`)
- `OAUTH_PATH`: Path to OAuth credentials (defaults to `secrets.json`)
- `FONT`: Defines text font (defaults to `Comic Sans MS`)

#### Default settings in `config/prompt.yml`
- `GET_CONTENT`: Guidelines for generating the transcript
- `GET_TITLE`: Guidelines for generating the title
- `GET_SEARCH_TERM`: YouTube search term used for background video scraping
- `GET_DESCRIPTION`: Guidelines for generating the description
- `GET_CATEGORY_ID`: Guidelines for generating Category ID for the video

## 📦 Installation
1. **Clone the repository**
```bash
git clone https://github.com/ecnivs/crank.git
cd crank
```
2. **Install `uv`**
```bash
pip install uv
```
3. **Install dependencies using `uv`**
```bash
uv sync
```
4. **Install `ffmpeg`**
```bash
# Debian / Ubuntu
sudo apt install ffmpeg

# Arch Linux
sudo pacman -S ffmpeg

# macOS (Homebrew)
brew install ffmpeg

# Windows (using Chocolatey)
choco install ffmpeg
```
5. **Install `spaCy` language model**
```bash
uv run python -m spacy download en_core_web_md
```


## 🚀 Running Crank
**Run the tool with the default configuration**
```bash
uv run main.py
```
**Or provide your custom config file with `--path`**
```bash
uv run main.py --path path/to/your_config.yml
```

## 📹 Example Output
<div align="center">

https://github.com/user-attachments/assets/69b1dc3d-79f2-4a6f-bde1-da6c07e32185

</div>

## 💖 Support the project
If you find Crank helpful and want to support its development, donations are welcome!
Your support helps keep the project active and enables new features.
<div align="center">
  <a href="https://www.buymeacoffee.com/ecnivs" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>
</div>

## 🧪 Testing
For information about running tests, see [TESTING.md](docs/TESTING.md).

## 🔌 Plugin Development
For information about creating custom background video plugins, see [PLUGIN_GUIDE.md](docs/PLUGIN_GUIDE.md).

## 🙌 Contributing
Feel free to:
1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Submit a pull request

#### *I'd appreciate any feedback or code reviews you might have!*
