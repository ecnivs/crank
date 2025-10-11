from google.auth.exceptions import RefreshError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, ResumableUploadError
from pathlib import Path
import datetime
import logging
from typing import Optional, Union, Dict, Any


class Uploader:
    """
    Handles uploading videos to YouTube using OAuth2 authentication.
    """

    def __init__(
        self, name: str = "crank", auth_token: Union[str, Path] = "secrets.json"
    ):
        """
        Initialize the uploader and authenticate with YouTube API.

        Args:
            name: Name of the channel/app used for token file naming.
            auth_token: Path to the OAuth2 client secrets JSON.
        """
        self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)
        self.name: str = name.replace(" ", "").lower()

        self.scopes: list[str] = ["https://www.googleapis.com/auth/youtube.upload"]

        self.secrets_file: Path = Path(auth_token)
        self.token_folder: Path = Path(".tokens")
        self.token_folder.mkdir(exist_ok=True)
        self.token_file: Path = self.token_folder / f"{self.name}_token.json"

        self.credentials: Optional[Credentials] = None
        self.service: Optional[Any] = None

        self._authenticate()

    def _authenticate(self) -> None:
        """
        Try authenticating with stored token or via OAuth flow.
        """
        try:
            self._try_authenticate()
        except RefreshError:
            self.logger.error("Refresh Failed. Delete token before retrying.")
            if self.token_file.exists():
                self.token_file.unlink()
            self.credentials = None
            self._try_authenticate()
        except Exception as e:
            raise RuntimeError(
                f"[{self.__class__.__name__}] Authentication Failed."
            ) from e

    def _try_authenticate(self) -> None:
        """
        Attempt authentication using stored credentials or OAuth flow.
        """
        if self.token_file.exists() and not self.credentials:
            self.credentials = Credentials.from_authorized_user_file(
                str(self.token_file), self.scopes
            )

        if not self.credentials or not self.credentials.valid:
            if (
                self.credentials
                and self.credentials.expired
                and self.credentials.refresh_token
            ):
                self.credentials.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.secrets_file), self.scopes
                )
                self.credentials = flow.run_local_server(port=0, open_browser=True)

            self.token_file.write_text(self.credentials.to_json(), encoding="utf-8")

        self.service = build("youtube", "v3", credentials=self.credentials)

    def upload(self, video_data: Dict[str, Any]) -> Optional[datetime.datetime]:
        """
        Upload a video to YouTube.

        Args:
            video_data: Dictionary containing:
                - video_path: Path to the video file (str or Path)
                - title: Video title
                - description: Video description
                - categoryId: YouTube category ID
                - delay: Delay in hours for scheduled publishing
                - last_upload: Last upload datetime (used for scheduling)

        Returns:
            datetime.datetime: Scheduled or actual publish time if successful.
            None: If the upload fails.
        """
        try:
            body: Dict[str, Any] = {
                "snippet": {
                    "title": f"{video_data.get('title', '')} #shorts",
                    "description": video_data.get(
                        "description", "Like and Subscribe!!"
                    ),
                    "categoryId": video_data.get("categoryId", 24),
                },
                "status": {"privacyStatus": "public"},
            }

            last_upload: datetime.datetime = video_data.get(
                "last_upload", datetime.datetime.now(datetime.UTC)
            )
            delay: int = video_data.get("delay", 0)
            scheduled_publish_time: datetime.datetime = (
                last_upload + datetime.timedelta(hours=delay)
            )
            now: datetime.datetime = datetime.datetime.now(datetime.UTC)

            if delay and scheduled_publish_time > now:
                body["status"]["publishAt"] = scheduled_publish_time.strftime(
                    "%Y-%m-%dT%H:%M:%S.000Z"
                )
                body["status"]["privacyStatus"] = "private"
            else:
                scheduled_publish_time = now
                body["status"]["privacyStatus"] = "public"

            media_path: Union[str, Path] = video_data.get("video_path")
            media = MediaFileUpload(str(media_path), mimetype="video/*", resumable=True)

            request = self.service.videos().insert(
                part="snippet,status", body=body, media_body=media
            )
            response = request.execute()

            self.logger.info(
                f"Uploaded successfully: https://www.youtube.com/watch?v={response['id']}"
            )
            return scheduled_publish_time

        except ResumableUploadError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to upload: {e}")
            return None
