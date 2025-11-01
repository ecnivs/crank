import logging
import datetime
from pathlib import Path
from googleapiclient.http import ResumableUploadError
import asyncio
from prompt import Prompt
import re
from typing import List, Dict, Any, Union


class Orchestrator:
    """
    Central controller for automated video generation and upload.
    Handles prompt creation, content generation, media assembly, and upload.
    """

    def __init__(
        self,
        preset: Any,
        scraper: Any,
        gemini: Any,
        editor: Any,
        caption: Any,
        uploader: Any,
    ) -> None:
        """
        Initialize the Orchestrator with module dependencies and configuration.

        Args:
            preset: Instance of configuration handler.
            scraper: Instance of a scraper module for retrieving visual media.
            gemini: Instance of the gemini module for content and script generation.
            editor: Instance of the video editor module for rendering final videos.
            caption: Instance of the captioning module for subtitle generation.
            uploader: Instance of the uploader module for publishing videos.
        """
        self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)

        self.preset: Any = preset
        self.scraper: Any = scraper
        self.gemini: Any = gemini
        self.editor: Any = editor
        self.caption: Any = caption
        self.uploader: Any = uploader

        self.prompt: Prompt = Prompt()

    def _upload(self, data: Dict[str, str], video_path: Union[str, Path]) -> None:
        """
        Prepares metadata and sends the final video to the uploader.
        Updates preset state.

        Args:
            data: Parsed Gemini response with title, description, etc.
            video_path: Path to the final rendered video file.
        """
        title: str = data.get("title", "")

        upload_dict: Dict[str, Any] = {
            "video_path": video_path,
            "title": title,
            "description": data.get("description", ""),
            "categoryId": data.get("categoryId", 24),
            "delay": self.preset.get("DELAY", 0),
            "last_upload": self.preset.get("LAST_UPLOAD"),
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

        current: List[str] = self.preset.get("USED_CONTENT") or []
        if title and title not in current:
            current.append(title.strip())
            self.preset.set("USED_CONTENT", current[-100:])

    def _process_task(self, data: Dict[str, str]) -> Path:
        """
        Handles the full video creation pipeline for a single content entry.

        Args:
            data: Dictionary containing parsed responses from gemini

        Returns:
            Path: path to final rendered video file
        """
        media_path = self.scraper.get_media(data.get("search_term", ""))
        audio_path = self.gemini.get_audio(transcript=data.get("transcript", ""))
        ass_path = self.caption.get_captions(audio_path=audio_path)

        video_path = self.editor.assemble(
            ass_path=ass_path, audio_path=audio_path, media_path=media_path
        )

        return video_path

    async def process(self, prompt: str) -> None:
        """
        Entry point for generating and uploading a video from a prompt.

        Args:
            prompt: Topic or keyword to build a video around.
        """
        response: str = self.prompt.build(prompt, self.preset.get("USED_CONTENT", []))
        text: str = self.gemini.get_response(response, 2.5)

        field_map: Dict[str, str] = {
            "TRANSCRIPT": "transcript",
            "DESCRIPTION": "description",
            "SEARCH_TERM": "search_term",
            "TITLE": "title",
            "CATEGORY_ID": "categoryId",
        }

        result: Dict[str, str] = {}
        for prefix, key in field_map.items():
            pattern = rf"{re.escape(prefix)}:\s*(.*?)(?=\n(?:TRANSCRIPT|DESCRIPTION|SEARCH_TERM|TITLE|CATEGORY_ID):|$)"
            match = re.search(pattern, text, re.DOTALL)
            result[key] = match.group(1).strip() if match else ""

        if not result.get("transcript"):
            transcript_pattern = r"^(Say\s+\w+:\s+.*?)(?=\n\s*(?:DESCRIPTION|SEARCH_TERM|TITLE|CATEGORY_ID):|$)"
            transcript_match = re.search(
                transcript_pattern, text, re.DOTALL | re.MULTILINE
            )
            if transcript_match:
                result["transcript"] = transcript_match.group(1).strip()
                self.logger.info(
                    "Extracted transcript using fallback pattern (missing TRANSCRIPT: prefix)"
                )
            else:
                first_label_pattern = (
                    r"^(.*?)(?=\n\s*(?:DESCRIPTION|SEARCH_TERM|TITLE|CATEGORY_ID):|$)"
                )
                first_label_match = re.search(
                    first_label_pattern, text, re.DOTALL | re.MULTILINE
                )
                if first_label_match:
                    potential_transcript = first_label_match.group(1).strip()
                    if "Say" in potential_transcript or len(potential_transcript) > 50:
                        result["transcript"] = potential_transcript
                        self.logger.info(
                            "Extracted transcript from beginning of response (missing TRANSCRIPT: prefix)"
                        )

        missing: List[str] = [k for k, v in result.items() if not v]
        if missing:
            self.logger.warning(f"Missing or empty fields: {missing}")
            if "transcript" in missing:
                self.logger.error(
                    f"Failed to extract transcript. Raw response: {text[:500]}..."
                )
                raise ValueError(
                    "Cannot proceed without transcript. Gemini response did not contain "
                    "TRANSCRIPT: field and fallback extraction failed."
                )

        video_path: Path = self._process_task(result)
        if self.uploader:
            self._upload(result, video_path=video_path)

        await asyncio.sleep(0.01)
