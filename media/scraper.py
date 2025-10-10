from pathlib import Path
import subprocess
import logging
import yt_dlp


class Scraper:
    def __init__(self, workspace):
        self.workspace = workspace
        self.logger = logging.getLogger(self.__class__.__name__)

    def _download_video(self, query, max_results=10):
        ydl_opts_search = {
            "quiet": True,
            "extract_flat": True,
            "skip_download": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts_search) as ydl:
            search_url = f"ytsearch{max_results}:{query}"
            info = ydl.extract_info(search_url, download=False)
            results = []
            if "entries" in info:
                for entry in info["entries"]:
                    video_id = entry.get("id")
                    if video_id and len(video_id) == 11:
                        results.append(f"https://www.youtube.com/watch?v={video_id}")

        if not results:
            raise ValueError(f"No results found for query: {query}")

        url = results[0]
        output_template = str(self.workspace / "%(id)s.%(ext)s")
        ydl_opts_download = {
            "outtmpl": output_template,
            "format": "bestvideo[height<=720][height>=480][ext=mp4]",
        }
        with yt_dlp.YoutubeDL(ydl_opts_download) as ydl:
            info = ydl.extract_info(url, download=True)
            video_path = Path(ydl.prepare_filename(info))
            if video_path.suffix != ".mp4":
                video_path = video_path.with_suffix(".mp4")
        return video_path

    def _get_video_duration(self, path):
        cmd = [
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

    def _clip_video(self, input_path):
        duration = self._get_video_duration(input_path)
        output_path = self.workspace / f"{input_path.stem}_short.mp4"

        vf_filters = "crop=ih*9/16:ih,scale=1080:1920,gblur=sigma=5,hflip"

        if duration >= 60:
            start_time = max(0, (duration / 2) - 30)
            cmd = [
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
            loops = int(60 / duration) + 1
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

    def get_media(self, term):
        video_path = self._download_video(term)
        short_path = self._clip_video(video_path)
        video_path.unlink(missing_ok=True)
        self.logger.info(f"Video template stored at {short_path}")
        return Path(short_path)
