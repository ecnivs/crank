import subprocess
import json
import logging
from pathlib import Path
from typing import Union


class Editor:
    """Handles assembling video from media, audio, and subtitles using FFmpeg."""

    def __init__(self, workspace: Union[str, Path]) -> None:
        """
        Initialize editor with working directory.

        Args:
            workspace: Path to workspace folder for temporary files.
        """
        self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)
        self.workspace: Path = Path(workspace)

    def _get_duration(self, file_path: Union[str, Path]) -> float:
        """
        Get duration of media file using FFprobe.

        Args:
            file_path: Path to media/audio file.

        Returns:
            float: Duration in seconds.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(
                f"[{self.__class__.__name__}] File not found: {file_path}"
            )

        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(file_path),
        ]

        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
            info = json.loads(output)
            duration = float(info["format"]["duration"])
            return duration
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"[{self.__class__.__name__}] FFprobe failed: {getattr(e, 'output', str(e))}"
            )
        except (KeyError, json.JSONDecodeError):
            raise RuntimeError(
                f"[{self.__class__.__name__}] Failed to parse FFprobe output for {file_path}"
            )

    def assemble(
        self,
        ass_path: Union[str, Path],
        audio_path: Union[str, Path],
        media_path: Union[str, Path],
    ) -> Path:
        """
        Assemble video from media, audio, and subtitle file.

        Args:
            ass_path: Path to .ass subtitle file.
            audio_path: Path to audio file.
            media_path: Path to video/image file.

        Returns:
            Path: Path to generated output video.
        """
        ass_path, audio_path, media_path = (
            Path(ass_path),
            Path(audio_path),
            Path(media_path),
        )
        output_path = Path(self.workspace / "output.mp4")

        for file_path, desc in [
            (ass_path, "ASS subtitle"),
            (audio_path, "Audio"),
            (media_path, "Media"),
        ]:
            if not file_path.exists():
                raise FileNotFoundError(
                    f"[{self.__class__.__name__}] {desc} file not found: {file_path}\n"
                    f"Please ensure all required files (subtitle, audio, media) are generated/available."
                )

        audio_duration = self._get_duration(audio_path)
        media_duration = self._get_duration(media_path)
        final_duration = min(audio_duration, media_duration, 60.0)

        if final_duration <= 0:
            raise ValueError(
                f"[{self.__class__.__name__}] Calculated video duration is not positive "
                f"(audio: {audio_duration:.2f}s, media: {media_duration:.2f}s). "
                f"Please check that both audio and video files are valid."
            )

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(media_path),
            "-i",
            str(audio_path),
            "-filter_complex",
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,"
            f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,ass={ass_path}[v]",
            "-map",
            "[v]",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-t",
            str(final_duration),
            str(output_path),
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            if not output_path.exists() or output_path.stat().st_size == 0:
                raise RuntimeError(
                    f"[{self.__class__.__name__}] Output video is empty or missing"
                )

            self.logger.info(f"Successfully generated output video: {output_path}")
            return output_path

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr or str(e)
            self.logger.error(f"FFmpeg failed: {error_msg}")
            raise RuntimeError(
                f"[{self.__class__.__name__}] Error while processing video: {error_msg}\n"
                f"This may indicate an issue with FFmpeg installation or the input files. "
                f"Please ensure FFmpeg is installed and the input files are valid."
            ) from e
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            raise RuntimeError(
                f"[{self.__class__.__name__}] Error while processing video: {e}"
            ) from e
