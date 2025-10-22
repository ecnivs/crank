import logging
import subprocess
from pathlib import Path
from http.cookiejar import MozillaCookieJar
from typing import Optional, List
import yt_dlp
import browser_cookie3


class Scraper:
    """
    Handles video scraping, downloading, clipping, and cookie management for YouTube.
    Automatically exports browser cookies to bypass bot detection.
    """

    def __init__(self, workspace: Path, cookies_file: Optional[Path] = None) -> None:
        """
        Initialize the scraper with a workspace and optional cookies file.

        Args:
            workspace: Directory to store downloaded videos and temporary files.
            cookies_file: Optional path to a cookies.txt file. If None, cookies are auto-exported.
        """
        self.workspace: Path = workspace
        self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)
        self.workspace.mkdir(exist_ok=True)

        self.cookies_file: Path = cookies_file or self._export_cookies_from_browser()
        self._last_cookie_refresh = None

    def _export_cookies_from_browser(self) -> Path:
        """
        Export YouTube cookies from installed browsers into a Mozilla-compatible cookies.txt file.

        Returns:
            Path: Path to the saved cookies file.
        """
        path: Path = self.workspace / "cookies.txt"
        cj: MozillaCookieJar = MozillaCookieJar(str(path))
        cookie_count = 0

        for reader in (browser_cookie3.chrome, browser_cookie3.firefox):
            try:
                jar = reader(domain_name=".youtube.com")
                for cookie in jar:
                    cj.set_cookie(cookie)
                    cookie_count += 1
            except Exception as e:
                self.logger.debug(f"Failed to read cookies from {reader.__name__}: {e}")
                continue

        cj.save()
        self.logger.info(f"Exported {cookie_count} cookies to {path}")
        self._last_cookie_refresh = path.stat().st_mtime
        return path

    def _refresh_cookies_if_needed(self) -> None:
        """
        Refresh cookies if they are older than 1 hour or don't exist.
        """
        import time

        if (
            not self.cookies_file.exists()
            or self._last_cookie_refresh is None
            or time.time() - self._last_cookie_refresh > 3600
        ):
            self.logger.info("Refreshing cookies...")
            self._export_cookies_from_browser()

    def _download_video(self, query: str, max_results: int = 10) -> Path:
        """
        Download a video from YouTube using yt_dlp with cookies.

        Args:
            query: Search term or URL to download.
            max_results: Number of search results to consider.

        Returns:
            Path: Path to the downloaded video file.
        """
        self._refresh_cookies_if_needed()

        ydl_opts_search = {
            "quiet": True,
            "extract_flat": True,
            "skip_download": True,
            "cookiefile": str(self.cookies_file),
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            },
            "sleep_interval": 1,
            "max_sleep_interval": 5,
            "sleep_interval_subtitles": 1,
        }

        query = f"Cinematic {query}"

        with yt_dlp.YoutubeDL(ydl_opts_search) as ydl:
            search_url: str = f"ytsearch{max_results}:{query}"
            info: dict = ydl.extract_info(search_url, download=False)
            results: List[str] = [
                f"https://www.youtube.com/watch?v={e['id']}"
                for e in info.get("entries", [])
                if e.get("id") and len(e["id"]) == 11
            ]
        if not results:
            raise ValueError(f"No results found for query: {query}")

        output_template: str = str(self.workspace / "%(id)s.%(ext)s")
        format_spec: str = (
            "bestvideo[height<=720][height>=480][ext=mp4]/"
            "bestvideo[height<=720][height>=480]/"
            "bestvideo[height<=1080][ext=mp4]/"
            "bestvideo[height<=1080]/"
            "best[ext=mp4]/"
            "best"
        )

        ydl_opts_download = {
            "outtmpl": output_template,
            "format": format_spec,
            "cookiefile": str(self.cookies_file),
            "quiet": True,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-us,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Accept-Charset": "ISO-8859-1,utf-8;q=0.7,*;q=0.7",
                "Connection": "keep-alive",
            },
            "sleep_interval": 1,
            "max_sleep_interval": 5,
            "sleep_interval_subtitles": 1,
            "retries": 3,
            "fragment_retries": 3,
            "ignoreerrors": False,
            "no_warnings": False,
            "extract_flat": False,
        }

        for i, url in enumerate(results):
            strategies = [
                ("original", ydl_opts_download),
                ("no_cookies", {**ydl_opts_download, "cookiefile": None}),
                (
                    "minimal",
                    {
                        "outtmpl": output_template,
                        "format": "best[ext=mp4]/best",
                        "quiet": True,
                        "http_headers": ydl_opts_download["http_headers"],
                    },
                ),
            ]

            for strategy_name, opts in strategies:
                try:
                    self.logger.info(
                        f"Attempting to download video {i + 1}/{len(results)} with {strategy_name} strategy: {url}"
                    )
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                        video_path: Path = Path(ydl.prepare_filename(info))
                        if video_path.suffix != ".mp4":
                            video_path = video_path.with_suffix(".mp4")
                        self.logger.info(
                            f"Successfully downloaded video with {strategy_name} strategy: {video_path}"
                        )
                        return video_path

                except Exception as e:
                    error_msg = str(e)
                    if "403" in error_msg or "Forbidden" in error_msg:
                        self.logger.warning(
                            f"403 Forbidden with {strategy_name} strategy for {url}: {e}"
                        )
                    elif "format is not available" in error_msg:
                        self.logger.warning(
                            f"Format not available with {strategy_name} strategy for {url}: {e}"
                        )
                    else:
                        self.logger.warning(
                            f"Other error with {strategy_name} strategy for {url}: {e}"
                        )
                    continue

        self.logger.warning(
            "All primary strategies failed, trying final fallback approaches..."
        )

        final_fallbacks = [
            (
                "ultra_minimal",
                {
                    "outtmpl": output_template,
                    "format": "best",
                    "quiet": True,
                },
            ),
            (
                "no_headers",
                {
                    "outtmpl": output_template,
                    "format": "best[ext=mp4]/best",
                    "quiet": True,
                    "cookiefile": str(self.cookies_file),
                },
            ),
        ]

        for fallback_name, opts in final_fallbacks:
            try:
                self.logger.info(
                    f"Trying final fallback: {fallback_name} for {results[0]}"
                )
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(results[0], download=True)
                    video_path: Path = Path(ydl.prepare_filename(info))
                    if video_path.suffix != ".mp4":
                        video_path = video_path.with_suffix(".mp4")
                    self.logger.info(
                        f"Successfully downloaded video with {fallback_name} fallback: {video_path}"
                    )
                    return video_path

            except Exception as e:
                self.logger.warning(f"Final fallback {fallback_name} also failed: {e}")
                continue

        self.logger.error("All download strategies failed")
        raise RuntimeError(
            f"Unable to download any video for query: {query}. All attempts failed."
        )

    def _get_video_duration(self, path: Path) -> float:
        """
        Get the duration of a video using ffprobe.

        Args:
            path: Path to the video file.

        Returns:
            float: Duration of the video in seconds.
        """
        cmd: List[str] = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        return float(result.stdout.strip())

    def _clip_video(self, input_path: Path) -> Path:
        """
        Clip a video to 60 seconds and apply filters like crop, scale, blur, and flip.

        Args:
            input_path: Path to the input video.

        Returns:
            Path: Path to the clipped video.
        """
        duration: float = self._get_video_duration(input_path)
        output_path: Path = self.workspace / f"{input_path.stem}_short.mp4"

        vf_filters: str = "crop=ih*9/16:ih,scale=1080:1920,gblur=sigma=5,hflip"

        if duration >= 60:
            start_time: float = max(0, (duration / 2) - 30)
            cmd: List[str] = [
                "ffmpeg",
                "-y",
                "-ss",
                str(start_time),
                "-i",
                str(input_path),
                "-t",
                "60",
                "-vf",
                vf_filters,
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "23",
                "-an",
                str(output_path),
            ]
        else:
            loops: int = int(60 / duration) + 1
            cmd = [
                "ffmpeg",
                "-y",
                "-stream_loop",
                str(loops),
                "-i",
                str(input_path),
                "-t",
                "60",
                "-vf",
                vf_filters,
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "23",
                "-an",
                str(output_path),
            ]

        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return output_path

    def get_media(self, term: str) -> Path:
        """
        Search, download, clip, and return path to the short video.

        Args:
            term: Search term for YouTube video content.

        Returns:
            Path: Path to the final clipped video.
        """
        video_path: Path = self._download_video(term)
        short_path: Path = self._clip_video(video_path)
        video_path.unlink(missing_ok=True)
        self.logger.info(f"Video template stored at {short_path}")
        return short_path
