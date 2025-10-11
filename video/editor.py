import subprocess
import json
import logging
from pathlib import Path
from typing import Union


class Editor:
    """
    Handles assembling video from media, audio, and subtitles using FFmpeg.
    Ensures proper scaling, padding, subtitle overlay, and duration limits.
    """

    def __init__(self, workspace: Union[str, Path]):
        """
        Initialize the editor with a working directory.

        Args:
            workspace: Path to the workspace folder for temporary files.
        """
        self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)
        self.workspace: Path = Path(workspace)

    def _get_duration(self, file_path: Union[str, Path]) -> float:
        """
        Get the duration of a media file using FFprobe.

        Args:
            file_path: Path to the media/audio file.

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
        Assemble a video from media, audio, and subtitle file.

        Args:
            ass_path: Path to the .ass subtitle file.
            audio_path: Path to the audio file.
            media_path: Path to the video/image file.

        Returns:
            Path: Path to the generated output video.
        """
        ass_path, audio_path, media_path = (
            Path(ass_path),
            Path(audio_path),
            Path(media_path),
        )
        output_path = self.workspace / "output.mp4"

        # Validate files
        for file_path, desc in [
            (ass_path, "ASS subtitle"),
            (audio_path, "Audio"),
            (media_path, "Media"),
        ]:
            if not file_path.exists():
                raise FileNotFoundError(
                    f"[{self.__class__.__name__}] {desc} not found: {file_path}"
                )

        audio_duration = self._get_duration(audio_path)
        media_duration = self._get_duration(media_path)
        final_duration = min(audio_duration, media_duration, 60.0)

        if final_duration <= 0:
            raise ValueError(
                f"[{self.__class__.__name__}] Calculated video duration is not positive"
            )

        # Build FFmpeg command
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(media_path),
            "-i",
            str(audio_path),
            "-filter_complex",
            f"[0:v]scale=720:1280:force_original_aspect_ratio=decrease,"
            f"pad=720:1280:(ow-iw)/2:(oh-ih)/2:color=black,ass={ass_path}[v]",
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
            self.logger.error(f"FFmpeg failed: {e.stderr or str(e)}")
            raise RuntimeError(
                f"[{self.__class__.__name__}] Error while processing video"
            ) from e
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            raise RuntimeError(
                f"[{self.__class__.__name__}] Error while processing video"
            ) from e
