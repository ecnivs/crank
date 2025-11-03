"""
Tests for youtube.Uploader class.
"""
import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.http import ResumableUploadError

from youtube import Uploader


class TestUploader:
    """Test suite for Uploader class."""

    @patch("youtube.uploader.InstalledAppFlow")
    @patch("youtube.uploader.build")
    def test_init_success(self, mock_build, mock_flow_class, temp_dir):
        """Test successful Uploader initialization."""
        secrets_file = temp_dir / "secrets.json"
        secrets_file.write_text('{"installed": {"client_id": "test", "client_secret": "secret", "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token"}}')
        
        mock_credentials = MagicMock(spec=Credentials)
        mock_credentials.valid = True
        mock_credentials.to_json.return_value = '{"token": "fake_token"}'
        mock_flow_instance = MagicMock()
        mock_flow_instance.run_local_server = MagicMock(return_value=mock_credentials)
        mock_flow_class.from_client_secrets_file.return_value = mock_flow_instance
        mock_build.return_value = MagicMock()
        
        token_dir = temp_dir / ".tokens"
        token_dir.mkdir(exist_ok=True)
        
        secrets_path_str = str(secrets_file)
        def path_exists(self):
            path_str = str(self)
            import os
            if path_str == secrets_path_str:
                return os.path.exists(secrets_path_str)
            return str(self).endswith("token.json")
        
        with patch.object(Path, "exists", path_exists), \
             patch("youtube.uploader.Credentials") as mock_creds_class:
            mock_creds_class.from_authorized_user_file.return_value = mock_credentials
            uploader = Uploader(name="test", auth_token=secrets_path_str)
            assert uploader.name == "test"
            assert uploader.secrets_file == secrets_file

    def test_init_secrets_file_not_found(self, temp_dir):
        """Test Uploader initialization with missing secrets file."""
        fake_secrets = temp_dir / "nonexistent.json"
        
        with pytest.raises(FileNotFoundError, match="OAuth secrets file not found"):
            Uploader(name="test", auth_token=str(fake_secrets))

    @patch("youtube.uploader.InstalledAppFlow")
    @patch("youtube.uploader.build", return_value=None)
    def test_upload_success(self, mock_build, mock_flow_class, temp_dir, mock_youtube_service):
        """Test successful video upload."""
        secrets_file = temp_dir / "secrets.json"
        secrets_file.write_text('{"installed": {"client_id": "test", "client_secret": "secret", "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token"}}')
        video_file = temp_dir / "test_video.mp4"
        video_file.write_bytes(b"fake_video_data")
        
        mock_build.return_value = mock_youtube_service
        
        mock_credentials = MagicMock(spec=Credentials)
        mock_credentials.valid = True
        mock_credentials.to_json.return_value = '{"token": "fake_token"}'
        
        mock_flow_instance = MagicMock()
        mock_flow_instance.run_local_server = MagicMock(return_value=mock_credentials)
        mock_flow_class.from_client_secrets_file.return_value = mock_flow_instance
        
        token_file = temp_dir / ".tokens" / "test_token.json"
        token_file.parent.mkdir(exist_ok=True)
        token_file.write_text('{"token": "fake_token", "refresh_token": "fake_refresh", "client_id": "test", "client_secret": "secret", "token_uri": "https://oauth2.googleapis.com/token"}')
        
        secrets_path_str = str(secrets_file)
        def path_exists_mock(self):
            path_str = str(self)
            import os
            if path_str == secrets_path_str:
                return os.path.exists(secrets_path_str)
            if "token" in path_str:
                return os.path.exists(path_str) if os.path.exists(os.path.dirname(path_str)) else True
            return False
        
        with patch.object(Path, "exists", path_exists_mock), \
             patch("youtube.uploader.Credentials") as mock_creds_class:
            mock_creds_class.from_authorized_user_file.return_value = mock_credentials
            uploader = Uploader(name="test", auth_token=secrets_path_str)
            uploader.service = mock_youtube_service
            
            video_data = {
                "video_path": video_file,
                "title": "Test Video",
                "description": "Test Description",
                "categoryId": 24,
                "delay": 0,
                "last_upload": None,
            }
            
            mock_response = {"id": "test_video_id"}
            mock_youtube_service.videos.return_value.insert.return_value.execute.return_value = mock_response
            
            url, scheduled = uploader.upload(video_data)
            assert url is not None
            assert "youtube.com" in url or "test_video_id" in url

    @patch("youtube.uploader.InstalledAppFlow")
    @patch("youtube.uploader.build", return_value=None)
    def test_upload_with_scheduling(self, mock_build, mock_flow_class, temp_dir, mock_youtube_service):
        """Test video upload with scheduling."""
        secrets_file = temp_dir / "secrets.json"
        secrets_file.write_text('{"installed": {"client_id": "test", "client_secret": "secret", "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token"}}')
        video_file = temp_dir / "test_video.mp4"
        video_file.write_bytes(b"fake_video_data")
        
        mock_build.return_value = mock_youtube_service
        
        mock_credentials = MagicMock(spec=Credentials)
        mock_credentials.valid = True
        mock_credentials.to_json.return_value = '{"token": "fake_token"}'
        
        mock_flow_instance = MagicMock()
        mock_flow_instance.run_local_server = MagicMock(return_value=mock_credentials)
        mock_flow_class.from_client_secrets_file.return_value = mock_flow_instance
        
        secrets_path_str = str(secrets_file)
        token_file = temp_dir / ".tokens" / "test_token.json"
        token_file.parent.mkdir(exist_ok=True)
        token_file.write_text('{"token": "fake_token", "refresh_token": "fake_refresh", "client_id": "test", "client_secret": "secret", "token_uri": "https://oauth2.googleapis.com/token"}')
        
        def path_exists_token(self):
            path_str = str(self)
            import os
            if path_str == secrets_path_str:
                return os.path.exists(secrets_path_str)
            if "token" in path_str:
                return os.path.exists(path_str) if os.path.exists(os.path.dirname(path_str)) else True
            return False
        
        with patch.object(Path, "exists", path_exists_token), \
             patch("youtube.uploader.Credentials") as mock_creds_class:
            mock_creds_class.from_authorized_user_file.return_value = mock_credentials
            uploader = Uploader(name="test", auth_token=secrets_path_str)
            uploader.service = mock_youtube_service
            
            last_upload = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=1)
            video_data = {
                "video_path": video_file,
                "title": "Test Video",
                "description": "Test Description",
                "categoryId": 24,
                "delay": 2,
                "last_upload": last_upload,
            }
            
            mock_response = {"id": "test_video_id"}
            mock_youtube_service.videos.return_value.insert.return_value.execute.return_value = mock_response
            
            url, scheduled = uploader.upload(video_data)
            assert scheduled is not None
            assert scheduled > last_upload

    @patch("youtube.uploader.InstalledAppFlow")
    @patch("youtube.uploader.build", return_value=None)
    def test_upload_resumable_error(self, mock_build, mock_flow_class, temp_dir, mock_youtube_service):
        """Test handling of ResumableUploadError."""
        secrets_file = temp_dir / "secrets.json"
        secrets_file.write_text('{"installed": {"client_id": "test", "client_secret": "secret", "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token"}}')
        video_file = temp_dir / "test_video.mp4"
        video_file.write_bytes(b"fake_video_data")
        
        mock_build.return_value = mock_youtube_service
        
        mock_credentials = MagicMock(spec=Credentials)
        mock_credentials.valid = True
        mock_credentials.to_json.return_value = '{"token": "fake_token"}'
        
        mock_flow_instance = MagicMock()
        mock_flow_instance.run_local_server = MagicMock(return_value=mock_credentials)
        mock_flow_class.from_client_secrets_file.return_value = mock_flow_instance
        
        secrets_path_str = str(secrets_file)
        token_file = temp_dir / ".tokens" / "test_token.json"
        token_file.parent.mkdir(exist_ok=True)
        token_file.write_text('{"token": "fake_token", "refresh_token": "fake_refresh", "client_id": "test", "client_secret": "secret", "token_uri": "https://oauth2.googleapis.com/token"}')
        
        def path_exists_token(self):
            path_str = str(self)
            import os
            if path_str == secrets_path_str:
                return os.path.exists(secrets_path_str)
            if "token" in path_str:
                return os.path.exists(path_str) if os.path.exists(os.path.dirname(path_str)) else True
            return False
        
        with patch.object(Path, "exists", path_exists_token), \
             patch("youtube.uploader.Credentials") as mock_creds_class:
            mock_creds_class.from_authorized_user_file.return_value = mock_credentials
            uploader = Uploader(name="test", auth_token=secrets_path_str)
            uploader.service = mock_youtube_service
            
            from unittest.mock import Mock
            mock_resp = Mock()
            mock_resp.status = 403
            mock_resp.reason = "Forbidden"
            error = ResumableUploadError(mock_resp, b"Forbidden")
            mock_youtube_service.videos.return_value.insert.return_value.execute.side_effect = error
            
            video_data = {
                "video_path": video_file,
                "title": "Test Video",
                "description": "Test Description",
                "categoryId": 24,
                "delay": 0,
                "last_upload": None,
            }
            
            with pytest.raises(ResumableUploadError):
                uploader.upload(video_data)

    @patch("youtube.uploader.InstalledAppFlow")
    @patch("youtube.uploader.build")
    def test_authenticate_refresh_error(self, mock_build, mock_flow_class, temp_dir):
        """Test authentication with refresh error."""
        secrets_file = temp_dir / "secrets.json"
        secrets_file.write_text('{"installed": {"client_id": "test", "client_secret": "secret", "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token"}}')
        
        with patch("youtube.uploader.Credentials") as mock_creds_class, \
             patch("google.auth.transport.requests.Request") as mock_request:
            mock_credentials = MagicMock(spec=Credentials)
            mock_credentials.valid = False
            mock_credentials.expired = True
            mock_credentials.refresh_token = "token"  # Has refresh token, so will try to refresh
            mock_credentials.to_json.return_value = '{"token": "fake_token"}'
            
            # Track refresh calls
            refresh_call_count = [0]
            def refresh_side_effect(*args, **kwargs):
                refresh_call_count[0] += 1
                if refresh_call_count[0] == 1:
                    # First refresh attempt fails
                    raise RefreshError("Token expired")
            
            mock_credentials.refresh = MagicMock(side_effect=refresh_side_effect)
            
            def from_authorized_user_file_side_effect(*args, **kwargs):
                return mock_credentials
            
            mock_creds_class.from_authorized_user_file = MagicMock(side_effect=from_authorized_user_file_side_effect)
            
            mock_new_creds = MagicMock()
            mock_new_creds.valid = True
            mock_new_creds.to_json.return_value = '{"token": "fake_token"}'
            mock_flow_instance = MagicMock()
            mock_flow_instance.run_local_server = MagicMock(return_value=mock_new_creds)
            mock_flow_class.from_client_secrets_file.return_value = mock_flow_instance
            
            def build_side_effect(*args, **kwargs):
                return MagicMock()
            
            mock_build.side_effect = build_side_effect
            
            token_file = temp_dir / ".tokens" / "test_token.json"
            token_file.parent.mkdir(exist_ok=True)
            token_file.write_text('{"token": "fake_token", "refresh_token": "fake_refresh", "client_id": "test", "client_secret": "secret", "token_uri": "https://oauth2.googleapis.com/token"}')
            
            secrets_path_str = str(secrets_file)
            def path_exists_mock(self):
                path_str = str(self)
                import os
                if path_str == secrets_path_str:
                    return os.path.exists(secrets_path_str)
                if path_str.endswith("token.json"):
                    return os.path.exists(path_str) if os.path.exists(os.path.dirname(path_str)) else False
                return False
            
            with patch.object(Path, "exists", path_exists_mock):
                uploader = Uploader(name="test", auth_token=secrets_path_str)
                assert uploader is not None
                # Verify that refresh was called
                assert refresh_call_count[0] > 0

