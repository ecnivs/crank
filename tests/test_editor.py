"""
Tests for video.Editor class.
"""

from pathlib import Path
from unittest.mock import Mock

import pytest

from src.video import Editor


class TestEditor:
    """Test suite for Editor class."""

    def test_init(self, temp_dir):
        """Test Editor initialization."""
        editor = Editor(workspace=temp_dir)
        assert editor.workspace == Path(temp_dir)

    def test_get_duration_success(self, temp_dir, mock_ffmpeg_probe):
        """Test successful duration retrieval."""
        editor = Editor(workspace=temp_dir)

        # Create a fake file
        test_file = temp_dir / "test.mp4"
        test_file.write_bytes(b"fake_video_data")

        duration = editor._get_duration(test_file)
        assert duration == 30.5

    def test_get_duration_file_not_found(self, temp_dir):
        """Test duration retrieval with non-existent file."""
        editor = Editor(workspace=temp_dir)
        fake_file = temp_dir / "nonexistent.mp4"

        with pytest.raises(FileNotFoundError):
            editor._get_duration(fake_file)

    def test_assemble_success(
        self,
        temp_dir,
        sample_audio_file,
        sample_video_file,
        sample_ass_file,
        mock_ffmpeg_probe,
        mock_ffmpeg_success,
    ):
        """Test successful video assembly."""
        editor = Editor(workspace=temp_dir)

        # Mock the output file creation
        output_path = temp_dir / "output.mp4"
        output_path.write_bytes(b"fake_output_video")

        result = editor.assemble(
            ass_path=sample_ass_file,
            audio_path=sample_audio_file,
            media_path=sample_video_file,
        )

        assert result == output_path
        assert result.exists()

    def test_assemble_with_options(
        self,
        temp_dir,
        sample_audio_file,
        sample_video_file,
        sample_ass_file,
        mock_ffmpeg_probe,
        monkeypatch,
    ):
        """Test assembly with background audio and suppressed captions."""
        import subprocess
        editor = Editor(workspace=temp_dir)
        
        output_path = temp_dir / "output.mp4"
        output_path.write_bytes(b"fake")
        
        bg_audio = temp_dir / "bg.mp3"
        bg_audio.write_bytes(b"fake")
        
        # Capture the command passed to subprocess.run
        captured_cmd = []
        def mock_run(cmd, **kwargs):
            captured_cmd.extend(cmd)
            result = Mock()
            result.returncode = 0
            return result
        monkeypatch.setattr(subprocess, "run", mock_run)

        editor.assemble(
            ass_path=sample_ass_file,
            audio_path=sample_audio_file,
            media_path=sample_video_file,
            background_audio_path=bg_audio,
            suppress_captions=True
        )
        
        cmd_str = " ".join(captured_cmd)
        
        # Verify background audio input
        assert "-i" in captured_cmd
        assert str(bg_audio) in captured_cmd
        
        # Verify audio mixing filter
        assert "amix=inputs=2" in cmd_str
        
        # Verify captions are NOT in the filter complex
        assert f"ass={sample_ass_file}" not in cmd_str

    def test_assemble_missing_ass_file(
        self, temp_dir, sample_audio_file, sample_video_file
    ):
        """Test assembly with missing ASS file."""
        editor = Editor(workspace=temp_dir)
        fake_ass = temp_dir / "missing.ass"

        with pytest.raises(FileNotFoundError, match="ASS subtitle"):
            editor.assemble(
                ass_path=fake_ass,
                audio_path=sample_audio_file,
                media_path=sample_video_file,
            )

    def test_assemble_missing_audio_file(
        self, temp_dir, sample_ass_file, sample_video_file
    ):
        """Test assembly with missing audio file."""
        editor = Editor(workspace=temp_dir)
        fake_audio = temp_dir / "missing.wav"

        with pytest.raises(FileNotFoundError, match="Audio"):
            editor.assemble(
                ass_path=sample_ass_file,
                audio_path=fake_audio,
                media_path=sample_video_file,
            )

    def test_assemble_missing_media_file(
        self, temp_dir, sample_ass_file, sample_audio_file
    ):
        """Test assembly with missing media file."""
        editor = Editor(workspace=temp_dir)
        fake_media = temp_dir / "missing.mp4"

        with pytest.raises(FileNotFoundError, match="Media"):
            editor.assemble(
                ass_path=sample_ass_file,
                audio_path=sample_audio_file,
                media_path=fake_media,
            )

    def test_assemble_invalid_duration(
        self,
        temp_dir,
        sample_ass_file,
        sample_audio_file,
        sample_video_file,
        monkeypatch,
    ):
        """Test assembly with invalid duration calculation."""
        editor = Editor(workspace=temp_dir)

        # Mock duration to return 0
        def mock_get_duration(file_path):
            return 0.0

        monkeypatch.setattr(editor, "_get_duration", mock_get_duration)

        with pytest.raises(ValueError, match="duration is not positive"):
            editor.assemble(
                ass_path=sample_ass_file,
                audio_path=sample_audio_file,
                media_path=sample_video_file,
            )

    def test_assemble_ffmpeg_failure(
        self,
        temp_dir,
        sample_ass_file,
        sample_audio_file,
        sample_video_file,
        mock_ffmpeg_probe,
        monkeypatch,
    ):
        """Test assembly when FFmpeg fails."""
        import subprocess

        editor = Editor(workspace=temp_dir)

        def mock_run_fail(cmd, **kwargs):
            result = Mock()
            result.returncode = 1
            result.stderr = "FFmpeg error: invalid codec"
            error = subprocess.CalledProcessError(1, cmd, stderr=result.stderr)
            result.check_returncode = Mock(side_effect=error)
            return result

        monkeypatch.setattr(subprocess, "run", mock_run_fail)

        with pytest.raises(RuntimeError, match="Error while processing video"):
            editor.assemble(
                ass_path=sample_ass_file,
                audio_path=sample_audio_file,
                media_path=sample_video_file,
            )
