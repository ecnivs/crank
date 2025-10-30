import logging
from pathlib import Path
from http.cookiejar import MozillaCookieJar
from typing import Optional, List, Dict, Any, Tuple
import yt_dlp
from . import processor as media_processor
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

    def _enrich_query(self, query: str) -> List[str]:
        """
        Enrich the incoming search term with visual modifiers and negatives.

        Args:
            query: Base search term.

        Returns:
            List[str]: Ordered query variants to try for YouTube search.
        """
        positive_modifiers: List[str] = [
            "cinematic",
            "b-roll",
            "slow motion",
            "macro",
            "aerial",
            "timelapse",
            "high contrast",
            "high motion",
            "establishing shot",
            "parallax",
            "tracking shot",
            "drone",
            "gimbal",
            "hyperlapse",
        ]
        negative_modifiers: List[str] = [
            "-talking head",
            "-podcast",
            "-news",
            "-reaction",
            "-gameplay",
            "-ui",
            "-compilation",
            "-asmr",
            "-commentary",
            "-shorts",
            "-tiktok",
            "-reels",
        ]

        import re
        base = re.sub(r"[^\w\s]", " ", query).strip()

        strong = f"{base} " + " ".join(positive_modifiers + negative_modifiers)
        light = f"{base} " + " ".join(["cinematic", "b-roll", "aerial", "timelapse"])
        minimal = base
        return [strong, light, minimal]

    def _extract_keywords(self, query: str) -> List[str]:
        """
        Extract core keywords from the user's query for relevance checks.

        Args:
            query: User search query.

        Returns:
            List[str]: Unique keywords of length >= 4.
        """
        import re
        base = re.sub(r"[^\w\s]", " ", query).lower()
        tokens = [t for t in base.split() if len(t) >= 4]
        seen: set = set()
        keywords: List[str] = []
        for t in tokens:
            if t not in seen:
                seen.add(t)
                keywords.append(t)
        return keywords

    def _relevance_score(self, entry: Dict[str, Any], keywords: List[str]) -> int:
        """
        Count how many query keywords appear in title/description/tags.

        Args:
            entry: yt-dlp metadata entry.
            keywords: List of keywords to match.

        Returns:
            int: Number of keywords found in metadata.
        """
        if not keywords:
            return 0
        title: str = (entry.get("title") or "").lower()
        description: str = (entry.get("description") or "").lower()
        tags_list: List[str] = entry.get("tags") or []
        tags = " ".join(tags_list).lower() if isinstance(tags_list, list) else ""
        text = f"{title} {description} {tags}"
        return sum(1 for k in keywords if k in text)

    def _score_entry(self, entry: Dict[str, Any]) -> float:
        """
        Compute a heuristic score for a search entry based on metadata.

        Args:
            entry: yt-dlp metadata entry.

        Returns:
            float: Quality score for the entry.
        """
        score: float = 0.0
        duration: Optional[float] = entry.get("duration")
        height: Optional[int] = None
        width: Optional[int] = None
        fps: Optional[float] = None

        formats: List[Dict[str, Any]] = entry.get("formats", []) or []
        for f in formats:
            if f.get("vcodec") != "none":
                h = f.get("height")
                if isinstance(h, int):
                    height = max(height or 0, h)
                w = f.get("width")
                if isinstance(w, int):
                    width = max(width or 0, w)
                if fps is None and isinstance(f.get("fps"), (int, float)):
                    fps = float(f["fps"])

        title: str = (entry.get("title") or "").lower()
        description: str = (entry.get("description") or "").lower()
        text: str = f"{title} {description}"

        positives = [
            "cinematic",
            "b-roll",
            "slow motion",
            "macro",
            "aerial",
            "timelapse",
            "high contrast",
            "high motion",
            "establishing shot",
            "parallax",
            "tracking shot",
            "drone",
            "gimbal",
            "hyperlapse",
        ]
        negatives = [
            "compilation",
            "meme",
            "asmr",
            "commentary",
            "podcast",
            "reaction",
            "shorts",
        ]

        if isinstance(duration, (int, float)):
            if duration >= 90:
                score += 3
            elif duration >= 60:
                score += 1

        if isinstance(height, int):
            if height >= 1080:
                score += 2
            elif height >= 720:
                score += 1

        if isinstance(fps, (int, float)) and 24 <= fps <= 60:
            score += 1

        if any(p in text for p in positives):
            score += 2
        if any(n in text for n in negatives):
            score -= 3

        if isinstance(width, int) and isinstance(height, int) and width > 0:
            if height > width * 1.05:
                score -= 4

        url = (entry.get("webpage_url") or "").lower()
        if "shorts" in url:
            score -= 4

        try:
            views = float(entry.get("view_count") or 0)
            import math
            score += min(3.0, math.log10(views + 1.0))
        except Exception:
            pass

        return score

    def _select_stream_url(self, meta: Dict[str, Any]) -> Optional[str]:
        """
        Pick a direct video URL from yt_dlp metadata for probing with ffmpeg.

        Args:
            meta: yt-dlp metadata dictionary.

        Returns:
            Optional[str]: Direct stream URL or None.
        """
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

    def _is_text_heavy(self, input_src: str, duration: float, threshold: float = 22.0) -> bool:
        """
        Determine if the video likely contains persistent burned-in text/overlays.

        Args:
            input_src: Path or URL to the video source.
            duration: Total duration of the source video.
            threshold: Text edge score threshold.

        Returns:
            bool: True if text overlays are detected above threshold.
        """
        target = min(60.0, duration)
        start, end, sub_score = media_processor.choose_best_window(input_src, duration, target)
        return sub_score > threshold

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
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Referer": "https://www.youtube.com/",
            },
            "sleep_interval": 1,
            "max_sleep_interval": 5,
            "sleep_interval_subtitles": 1,
            "retries": 3,
            "geo_bypass": True,
            "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
        }

        query_variants = self._enrich_query(query)

        entries: List[Dict[str, Any]] = []
        tried: List[str] = []
        with yt_dlp.YoutubeDL(ydl_opts_search) as ydl:
            for q in query_variants:
                search_url: str = f"ytsearch{max_results}:{q}"
                tried.append(q)
                try:
                    info: dict = ydl.extract_info(search_url, download=False)
                    entries = [
                        e for e in info.get("entries", []) if e.get("id") and len(e.get("id", "")) == 11
                    ]
                    if entries:
                        self.logger.info(f"Found {len(entries)} candidates for query variant")
                        break
                except Exception as e:
                    self.logger.debug(f"Search failed for variant '{q}': {e}")
                    continue

        if not entries:
            raise ValueError(
                "No results found for query: " + (query_variants[0] if query_variants else query)
            )

        detailed: List[Dict[str, Any]] = []
        with yt_dlp.YoutubeDL({**ydl_opts_search, "extract_flat": False}) as ydl:
            for idx, e in enumerate(entries[: max_results], start=1):
                url = f"https://www.youtube.com/watch?v={e['id']}"
                try:
                    self.logger.info(f"Fetching metadata {idx}/{min(len(entries), max_results)}: {url}")
                    meta = ydl.extract_info(url, download=False)
                    if meta:
                        detailed.append(meta)
                except Exception as e:
                    self.logger.debug(f"Metadata fetch failed for {url}: {e}")
                    continue

        if not detailed:
            raise ValueError("Failed to retrieve metadata for candidates")

        keywords = self._extract_keywords(query)
        if keywords:
            relevant = [d for d in detailed if self._relevance_score(d, keywords) >= 1]
            if relevant:
                detailed = relevant
                self.logger.info(f"Filtered to {len(detailed)} relevant candidates using keywords: {keywords}")

        def _combined_key(d: Dict[str, Any]) -> Tuple[int, float]:
            return (self._relevance_score(d, keywords), self._score_entry(d))

        ranked = sorted(detailed, key=_combined_key, reverse=True)

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
                "Referer": "https://www.youtube.com/",
            },
            "sleep_interval": 1,
            "max_sleep_interval": 5,
            "sleep_interval_subtitles": 1,
            "retries": 3,
            "fragment_retries": 3,
            "ignoreerrors": False,
            "no_warnings": False,
            "extract_flat": False,
            "continuedl": False,
            "geo_bypass": True,
            "concurrent_fragment_downloads": 4,
            "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
        }

        max_try = min(len(ranked), 4)
        for i, meta in enumerate(ranked[:max_try]):
            url = meta.get("webpage_url") or f"https://www.youtube.com/watch?v={meta.get('id')}"
            probe_url = self._select_stream_url(meta) or url
            vid_duration = float(meta.get("duration") or 0)
            if vid_duration <= 0:
                try:
                    vid_duration = self._get_video_duration(Path(url))
                except Exception:
                    vid_duration = 0

            try:
                if vid_duration > 0 and self._is_text_heavy(probe_url, vid_duration):
                    self.logger.info(f"Skipping {url} due to detected on-screen text overlays")
                    continue
            except Exception as check_err:
                self.logger.debug(f"Subtitle pre-check failed: {check_err}")

            start_time, end_time, _ = (0.0, 60.0, 0.0)
            if vid_duration > 0:
                try:
                    self.logger.info(f"Selecting best window for candidate {i+1}/{max_try}")
                    start_time, end_time, _ = media_processor.choose_best_window(probe_url, vid_duration, 60.0)
                except Exception as win_err:
                    self.logger.debug(f"Window selection failed, using default: {win_err}")

            strategies = [
                ("original", ydl_opts_download),
                ("no_cookies", {**ydl_opts_download, "cookiefile": None}),
                (
                    "no_headers_primary",
                    {
                        "outtmpl": output_template,
                        "format": "best[ext=mp4]/best",
                        "quiet": True,
                        "cookiefile": str(self.cookies_file),
                    },
                ),
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
                        f"Attempting to download video {i + 1}/{len(ranked)} with {strategy_name} strategy: {url}"
                    )
                    section = f"*{max(0.0, start_time):.3f}-{max(0.0, end_time):.3f}"
                    dl_stats: Dict[str, Any] = {"downloaded_bytes": 0, "total_bytes": None}

                    def _hook(d: Dict[str, Any]) -> None:
                        if d.get("status") == "downloading":
                            val = d.get("downloaded_bytes")
                            if isinstance(val, (int, float)):
                                dl_stats["downloaded_bytes"] = max(dl_stats["downloaded_bytes"], int(val))
                            if isinstance(d.get("total_bytes"), (int, float)):
                                dl_stats["total_bytes"] = int(d["total_bytes"])  # type: ignore[index]
                            elif isinstance(d.get("total_bytes_estimate"), (int, float)):
                                dl_stats["total_bytes"] = int(d["total_bytes_estimate"])  # type: ignore[index]

                    with yt_dlp.YoutubeDL({**opts, "download_sections": section, "progress_hooks": [_hook]}) as ydl:
                        info = ydl.extract_info(url, download=True)
                        video_path: Path = Path(ydl.prepare_filename(info))
                        if video_path.suffix != ".mp4":
                            video_path = video_path.with_suffix(".mp4")
                        try:
                            bytes_dl = int(dl_stats.get("downloaded_bytes") or 0)
                            total = dl_stats.get("total_bytes")
                            if isinstance(total, int) and total > 0:
                                pct = (bytes_dl / total) * 100
                                self.logger.info(
                                    f"Accepted video: {video_path} | downloaded ~{bytes_dl/1_000_000:.2f} MB (~{pct:.1f}% of stream)"
                                )
                            else:
                                self.logger.info(
                                    f"Accepted video: {video_path} | downloaded ~{bytes_dl/1_000_000:.2f} MB"
                                )
                        except Exception:
                            self.logger.info(f"Accepted video: {video_path}")
                        return video_path

                except Exception as e:
                    error_msg = str(e)
                    if "403" in error_msg or "Forbidden" in error_msg:
                        self.logger.warning(
                            f"403 Forbidden with {strategy_name} strategy for {url}: {e} — refreshing cookies and retrying"
                        )
                        try:
                            self._export_cookies_from_browser()
                            with yt_dlp.YoutubeDL({**opts, "download_sections": section}) as ydl2:
                                info = ydl2.extract_info(url, download=True)
                                video_path: Path = Path(ydl2.prepare_filename(info))
                                if video_path.suffix != ".mp4":
                                    video_path = video_path.with_suffix(".mp4")
                                self.logger.info(f"Accepted video after cookie refresh: {video_path}")
                                return video_path
                        except Exception as e2:
                            self.logger.warning(f"Retry after cookie refresh failed: {e2}")
                    elif "format is not available" in error_msg:
                        self.logger.warning(
                            f"Format not available with {strategy_name} strategy for {url}: {e}"
                        )
                    else:
                        self.logger.warning(
                            f"Other error with {strategy_name} strategy for {url}: {e}"
                        )
                    continue

        self.logger.warning("All primary strategies failed, trying final fallback approaches...")

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
                first_url = ranked[0].get("webpage_url") or f"https://www.youtube.com/watch?v={ranked[0].get('id')}"
                self.logger.info(f"Trying final fallback: {fallback_name} for {first_url}")
                section = f"*{max(0.0, start_time):.3f}-{max(0.0, end_time):.3f}"
                with yt_dlp.YoutubeDL({**opts, "download_sections": section}) as ydl:
                    info = ydl.extract_info(first_url, download=True)
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


    def _clip_video(self, input_path: Path) -> Path:
        """
        Delegate video processing to media.processor to build the final 1080x1920 short.

        Args:
            input_path: Path to the input video.

        Returns:
            Path: Path to the clipped video.
        """
        return media_processor.process_to_short(input_path, self.workspace)

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
