import logging
import datetime
from pathlib import Path
from googleapiclient.http import ResumableUploadError
import asyncio
from prompt import Prompt
import re
from typing import List, Dict


class Orchastrator:
    def __init__(self, preset, scraper, gemini, editor, caption, uploader) -> None:
        """
        Orachastrates video generation and upload.

        Args:
            preset: Crank config
            scraper: Instance of scraper module
            gemini: Instance of gemini module
            editor: Instance of editor module
            caption: Instance of caption module
            Uploader: Instance of uploader module
        """
        self.logger: logging.Logger = logging.getLogger(__class__.__name__)

        self.preset = preset
        self.scraper = scraper
        self.gemini = gemini
        self.editor = editor
        self.caption = caption
        self.uploader = uploader

        self.prompt: Prompt = Prompt()

    def _upload(self, data, video_path) -> None:
        """
        Stores the video and details in a dictionary and sends it to the uploader.

        Args:
            data: Dictionary containing parsed responses from gemini
            video_path: Path where the generated video is stored
        """
        title: str = data.get("title")

        upload_dict = {
            "video_path": video_path,
            "title": title,
            "description": data.get("description", ""),
            "categoryId": data.get("categoryId", 24),
            "delay": self.preset.get("DELAY", 0),
            "last_upload": self.preset.get("LAST_UPLOAD")
            or datetime.datetime.now(datetime.UTC),
        }
        try:
            self.preset.set(
                "LAST_UPLOAD",
                self.uploader.upload(video_data=upload_dict),
            )
        except ResumableUploadError:
            self.preset.set(
                "LIMIT_TIME", str(datetime.datetime.now(datetime.UTC).isoformat())
            )
            self.logger.warning("Upload limit reached")

        current: List = self.preset.get("USED_CONTENT") or []
        if title and title not in current:
            current.append(title.strip())
            self.preset.set("USED_CONTENT", current[-100:])

    def _process_task(self, data) -> None:
        """
        Orachastrates generation and assembly of video template, voiceover, captions and forwards it for upload.

        Args:
            data: Dictionary containing parsed responses from gemini
        """
        media_path: Path = self.scraper.get_media(data.get("search_term"))
        audio_path: Path = self.gemini.get_audio(transcript=data.get("transcript"))
        ass_path: Path = self.caption.get_captions(audio_path=audio_path)

        video_path: Path = self.editor.assemble(
            ass_path=ass_path, audio_path=audio_path, media_path=media_path
        )

        if self.uploader:
            self._upload(data, video_path=video_path)

    async def process(self, prompt) -> None:
        """
        Gets and parses gemini response and forwards it for video generation.

        Args:
            prompt: topic for the video
        """
        response: str = self.prompt.build(prompt)
        text: str = self.gemini.get_response(response, 2.5)

        field_map = {
            "TRANSCRIPT": "transcript",
            "DESCRIPTION": "description",
            "SEARCH_TERM": "search_term",
            "TITLE": "title",
            "CATEGORY_ID": "categoryId",
        }

        result: Dict = {}
        for prefix, key in field_map.items():
            pattern = rf"{re.escape(prefix)}:\s*(.*?)(?=\n(?:TRANSCRIPT|DESCRIPTION|SEARCH_TERM|TITLE|CATEGORY_ID):|$)"
            match = re.search(pattern, text, re.DOTALL)
            if match:
                result[key] = match.group(1).strip()
            else:
                result[key] = ""

        if missing := [k for k, v in result.items() if not v]:
            self.logger.warning(f"Missing or empty fields: {missing}")

        self._process_task(result)

        await asyncio.sleep(0.01)
