import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
import yt_dlp

from . import processor as vp


class Downloader:
    def __init__(self, workspace: Path, cookies_file: Optional[Path] = None) -> None:
        self.workspace: Path = workspace
        self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)
        self.workspace.mkdir(exist_ok=True)
        self.cookies_file: Optional[Path] = cookies_file

    def _select_stream_url(self, meta: Dict[str, Any]) -> Optional[str]:
        formats: List[Dict[str, Any]] = meta.get("formats", []) or []
        best_under_720: Tuple[int, str] = (0, "")
        best_any: Tuple[int, str] = (0, "")
        for f in formats:
            if f.get("vcodec") == "none":
                continue
            url = f.get("url")
            if not url:
                continue
            height = int(f.get("height") or 0)
            ext = (f.get("ext") or "").lower()
            if ext not in ("mp4", "m4v", "webm", "mov"):
                continue
            score = min(height, 1080)
            if height <= 720 and score > best_under_720[0]:
                best_under_720 = (score, url)
            if score > best_any[0]:
                best_any = (score, url)
        return (best_under_720[1] or best_any[1]) or None

    def download_section(self, url: str, meta: Dict[str, Any], cookies_file: Optional[Path]) -> Path:
        outtmpl: str = str(self.workspace / "%(id)s.%(ext)s")
        format_spec: str = (
            "bestvideo[height<=720][height>=480][ext=mp4]/"
            "bestvideo[height<=720][height>=480]/"
            "bestvideo[height<=1080][ext=mp4]/"
            "bestvideo[height<=1080]/"
            "best[ext=mp4]/best"
        )

        ydl_opts_base = {
            "outtmpl": outtmpl,
            "format": format_spec,
            "cookiefile": str(cookies_file) if cookies_file else None,
            "quiet": True,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-us,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Accept-Charset": "ISO-8859-1,utf-8;q=0.7,*;q=0.7",
                "Connection": "keep-alive",
                "Referer": "https://www.youtube.com/",
            },
            "retries": 3,
            "fragment_retries": 3,
            "ignoreerrors": False,
            "no_warnings": False,
            "extract_flat": False,
            "continuedl": False,
            "geo_bypass": True,
            "concurrent_fragment_downloads": 4,
        }

        duration = float(meta.get("duration") or 0)
        probe_url = self._select_stream_url(meta) or url
        start_time, end_time, _ = (0.0, min(60.0, duration or 60.0), 0.0)
        if duration > 0:
            try:
                self.logger.info("Selecting best window for candidate 1/1")
                start_time, end_time, _ = vp.choose_best_window(probe_url, duration, 60.0)
            except Exception as e:
                self.logger.debug(f"Window selection failed, using default: {e}")

        section = f"*{max(0.0, start_time):.3f}-{max(0.0, end_time):.3f}"
        with yt_dlp.YoutubeDL({**ydl_opts_base, "download_sections": section}) as ydl:
            info = ydl.extract_info(url, download=True)
            video_path = Path(ydl.prepare_filename(info))
            if video_path.suffix != ".mp4":
                video_path = video_path.with_suffix(".mp4")
            self.logger.info(f"Accepted video: {video_path}")
            return video_path


