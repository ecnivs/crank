import os
import subprocess
import json
import logging


class Editor:
    def __init__(self, workspace):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.workspace = workspace

    def _get_duration(self, file_path):
        if not os.path.exists(file_path):
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
            file_path,
        ]
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
            info = json.loads(output)

            if "format" not in info or "duration" not in info["format"]:
                raise RuntimeError(
                    f"[{self.__class__.__name__}] Could not extract duration from {file_path}"
                )

            return float(info["format"]["duration"])
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"[{self.__class__.__name__}] FFprobe failed: {e.output.decode() if hasattr(e, 'output') else str(e)}"
            )
        except json.JSONDecodeError:
            raise RuntimeError(
                f"[{self.__class__.__name__}] Failed to parse FFprobe output for {file_path}"
            )
        except Exception:
            raise RuntimeError(
                f"[{self.__class__.__name__}] Error while getting audio duration"
            )

    def assemble(self, ass_path, audio_path, media_path):
        output_path = self.workspace / "output.mp4"

        for file_path, file_desc in [
            (ass_path, "ASS subtitle file"),
            (audio_path, "Audio file"),
            (media_path, "Media file"),
        ]:
            if not os.path.exists(file_path):
                raise FileNotFoundError(
                    f"[{self.__class__.__name__}] {file_desc} not found: {file_path}"
                )

        try:
            audio_duration = self._get_duration(audio_path)
            media_duration = self._get_duration(media_path)
            final_duration = min(audio_duration, media_duration)
            final_duration = min(final_duration, 60.0)
            if final_duration <= 0:
                raise ValueError(
                    f"[{self.__class__.__name__}] Calculated video duration is not positive"
                )

            cmd = ["ffmpeg", "-y"]
            cmd.extend(["-i", media_path])
            cmd.extend(["-i", audio_path])
            video_filter = f"[0:v]scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2:color=black,ass={ass_path}[v]"
            cmd.extend(["-filter_complex", video_filter])
            cmd.extend(["-map", "[v]"])
            cmd.extend(["-map", "1:a:0"])
            cmd.extend(
                [
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
                    output_path,
                ]
            )
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                raise RuntimeError(
                    f"[{self.__class__.__name__}] Failed to generate output video (file is empty or doesn't exist)"
                )
            self.logger.info(f"Successfully generated output video to {output_path}")
            return output_path

        except subprocess.CalledProcessError as e:
            error_output = e.stderr if e.stderr else str(e)
            self.logger.error(f"FFmpeg command failed: {error_output}")
            raise RuntimeError(
                f"[{self.__class__.__name__}] Error while processing video: {error_output}"
            )

        except Exception as e:
            self.logger.error(f"Unexpected error: {str(e)}")
            raise RuntimeError(
                f"[{self.__class__.__name__}] Error while processing video"
            ) from e
