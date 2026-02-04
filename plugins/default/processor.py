"""Video processing logic for the default plugin."""

import logging
import subprocess
import random
from pathlib import Path
from typing import List, Tuple


class VideoProcessor:
    """Handles video processing operations like scene detection, montage creation, and ffmpeg operations."""

    def __init__(self, workspace: Path) -> None:
        """Initialize the video processor.

        Args:
            workspace: Directory for temporary files and output.
        """
        self.workspace: Path = workspace
        self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)

    def get_video_duration(self, path: Path) -> float:
        """Get duration of video using ffprobe.

        Args:
            path: Path to video file.

        Returns:
            float: Duration in seconds.
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

    def probe_scene_cuts(
        self, input_src: str, scene_threshold: float = 0.35
    ) -> List[float]:
        """Use ffmpeg to detect scene change timestamps.

        Args:
            input_src: Path or URL to video source.
            scene_threshold: Threshold for scene detection.

        Returns:
            List[float]: List of scene cut timestamps in seconds.
        """
        cmd: List[str] = [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(input_src),
            "-vf",
            f"select='gt(scene,{scene_threshold})',showinfo",
            "-f",
            "null",
            "-",
        ]
        try:
            proc = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
        except Exception:
            return []
        cuts: List[float] = []
        for line in proc.stderr.splitlines():
            if "showinfo" in line and "pts_time:" in line:
                try:
                    ts = float(line.split("pts_time:")[1].split(" ")[0])
                    cuts.append(ts)
                except Exception:
                    continue
        return cuts

    def band_edge_score(
        self, input_src: str, start: float, duration: float, band: str
    ) -> float:
        """Estimate text/overlay presence in vertical band by measuring edge activity.

        Args:
            input_src: Path or URL to the video source.
            start: Start time in seconds.
            duration: Duration to sample in seconds.
            band: Vertical band to sample ("top", "mid", or "bottom").

        Returns:
            float: Edge score; higher values indicate more text-like content.
        """
        if band == "top":
            crop_expr = "crop=iw:ih*0.35:0:0"
        elif band == "mid":
            crop_expr = "crop=iw:ih*0.35:0:ih*0.325"
        else:
            crop_expr = "crop=iw:ih*0.35:0:ih*0.65"
        cmd: List[str] = [
            "ffmpeg",
            "-hide_banner",
            "-ss",
            f"{max(0.0, start):.3f}",
            "-t",
            f"{max(0.1, duration):.3f}",
            "-i",
            str(input_src),
            "-vf",
            f"fps=1,{crop_expr},format=gray,sobel,signalstats,metadata=print",
            "-f",
            "null",
            "-",
        ]
        try:
            proc = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
        except Exception:
            return 0.0

        values: List[float] = []
        for line in (proc.stderr or "").splitlines():
            if "lavfi.signalstats.YAVG" in line:
                try:
                    part = line.split("lavfi.signalstats.YAVG:")[1].split(" ")[0]
                    values.append(float(part))
                except Exception:
                    continue
        if not values:
            return 0.0
        return sum(values) / len(values)

    def choose_best_window(
        self, input_src: str, duration: float, target: float = 60.0
    ) -> Tuple[float, float, float]:
        """Choose best start time for target-duration window based on scene cuts and text scores.

        Args:
            input_src: Path or URL to video source.
            duration: Total duration of source video.
            target: Target window duration in seconds.

        Returns:
            Tuple[float, float, float]: (start_time, end_time, text_score).
        """
        if duration <= target:
            score = max(
                self.band_edge_score(input_src, 0.0, duration, "top"),
                self.band_edge_score(input_src, 0.0, duration, "mid"),
                self.band_edge_score(input_src, 0.0, duration, "bottom"),
            )
            return 0.0, min(duration, target), score

        scene_cuts = self.probe_scene_cuts(input_src)
        num_candidates = 8
        step = max(1.0, (duration - target) / max(1, num_candidates - 1))
        best: Tuple[float, float, float, float] = (-1.0, -1.0, float("inf"), -1.0)

        def edge_distance(t: float) -> float:
            if not scene_cuts:
                return 999.0
            return min(abs(t - c) for c in scene_cuts)

        for i in range(num_candidates):
            start_time = i * step
            end_time = start_time + target
            if end_time > duration:
                break
            if edge_distance(start_time) < 0.7 or edge_distance(end_time) < 0.7:
                continue
            sub_score = max(
                self.band_edge_score(input_src, start_time, min(10.0, target), "top"),
                self.band_edge_score(input_src, start_time, min(10.0, target), "mid"),
                self.band_edge_score(
                    input_src, start_time, min(10.0, target), "bottom"
                ),
            )
            border_clearance = min(edge_distance(start_time), edge_distance(end_time))
            objective = (border_clearance) - (sub_score * 0.05)
            if best[3] < objective:
                best = (start_time, end_time, sub_score, objective)

        if best[0] < 0:
            mid_start = max(0.0, (duration - target) / 2)
            sub_score = max(
                self.band_edge_score(input_src, mid_start, min(10.0, target), "top"),
                self.band_edge_score(input_src, mid_start, min(10.0, target), "mid"),
                self.band_edge_score(input_src, mid_start, min(10.0, target), "bottom"),
            )
            return mid_start, mid_start + target, sub_score

        return best[0], best[1], best[2]

    def select_montage_segments(
        self,
        input_src: str,
        duration: float,
        max_segment_len: float = 7.0,
        total_target: float = 60.0,
    ) -> List[Tuple[float, float]]:
        """Select multiple short segments approximating total_target seconds.

        Args:
            input_src: Path or URL to video source.
            duration: Total duration of source video.
            max_segment_len: Maximum length of each segment in seconds.
            total_target: Total target duration for all segments.

        Returns:
            List[Tuple[float, float]]: List of (start, end) tuples in seconds.
        """
        cuts = self.probe_scene_cuts(input_src)

        def is_near_cut(t: float) -> bool:
            if not cuts:
                return False
            return min(abs(t - c) for c in cuts) < 0.7

        segments: List[Tuple[float, float]] = []
        picked_time: float = 0.0
        grid_step = max_segment_len
        i = 0
        while picked_time < min(total_target, duration) and i * grid_step < duration:
            base_start = i * grid_step + random.uniform(-0.5, 0.5)
            candidates: List[Tuple[float, float, float]] = []
            offsets = [-1.5, -0.8, 0.0, 0.8, 1.5]
            random.shuffle(offsets)
            for offset in offsets:
                start = max(0.0, min(duration - 0.5, base_start + offset))
                end = min(duration, start + max_segment_len)
                if end - start < 1.5:
                    continue
                if is_near_cut(start) or is_near_cut(end):
                    continue
                score = max(
                    self.band_edge_score(
                        input_src, start, min(3.0, end - start), "top"
                    ),
                    self.band_edge_score(
                        input_src, start, min(3.0, end - start), "mid"
                    ),
                    self.band_edge_score(
                        input_src, start, min(3.0, end - start), "bottom"
                    ),
                )
                candidates.append((score, start, end))

            if candidates:
                candidates.sort(key=lambda x: x[0])
                _, start, end = candidates[0]
                if not segments or start >= segments[-1][1] - 0.1:
                    segments.append((start, end))
                    picked_time += end - start
            i += 1

        trimmed: List[Tuple[float, float]] = []
        acc = 0.0
        for s, e in segments:
            seg_len = e - s
            if acc + seg_len <= total_target:
                trimmed.append((s, e))
                acc += seg_len
            else:
                remain = max(0.0, total_target - acc)
                if remain >= 1.0:
                    trimmed.append((s, s + remain))
                    acc += remain
                break

        return trimmed or [(0.0, min(duration, max_segment_len))]

    def process_to_short(self, input_path: Path) -> Path:
        """Process downloaded video into final 1080x1920 Short using montage segments.

        Args:
            input_path: Path to input video file.

        Returns:
            Path: Path to final processed video.
        """
        duration: float = self.get_video_duration(input_path)
        output_path: Path = self.workspace / f"{input_path.stem}_short.mp4"

        segments = self.select_montage_segments(
            str(input_path),
            duration,
            max_segment_len=7.0,
            total_target=min(60.0, duration),
        )

        total_seg_duration = sum(e - s for s, e in segments)

        if total_seg_duration < 60.0:
            loops_needed = int(60.0 / total_seg_duration) + 1
            trim_parts: List[str] = []
            seg_labels: List[str] = []
            for loop_idx in range(loops_needed):
                for idx, (s, e) in enumerate(segments, start=1):
                    seg_label = f"[s{loop_idx}_{idx}]"
                    trim_parts.append(
                        f"[0:v]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS{seg_label}"
                    )
                    seg_labels.append(seg_label)

            concat_inputs = "".join(seg_labels)
            filter_complex = ";".join(
                trim_parts
                + [
                    f"{concat_inputs}concat=n={len(seg_labels)}:v=1:a=0[vcat]",
                    "[vcat]crop=ih*9/16:ih:(iw-ow)/2:(ih-oh)/2,scale=1080:1920:flags=lanczos,unsharp=5:5:0.6:5:5:0.0,hflip[vf]",
                ]
            )

            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                str(input_path),
                "-filter_complex",
                filter_complex,
                "-map",
                "[vf]",
                "-t",
                "60",
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
            trim_parts: List[str] = []
            seg_labels: List[str] = []
            for idx, (s, e) in enumerate(segments, start=1):
                seg_label = f"[s{idx}]"
                trim_parts.append(
                    f"[0:v]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS{seg_label}"
                )
                seg_labels.append(seg_label)

            concat_inputs = "".join(seg_labels)
            filter_complex = ";".join(
                trim_parts
                + [
                    f"{concat_inputs}concat=n={len(seg_labels)}:v=1:a=0[vcat]",
                    "[vcat]crop=ih*9/16:ih:(iw-ow)/2:(ih-oh)/2,scale=1080:1920:flags=lanczos,unsharp=5:5:0.6:5:5:0.0,hflip[vf]",
                ]
            )

            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                str(input_path),
                "-filter_complex",
                filter_complex,
                "-map",
                "[vf]",
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
