import logging
import datetime
from pathlib import Path
from googleapiclient.http import ResumableUploadError
import asyncio
from prompt import Prompt
from preset import YmlHandler
from media import Scraper
from response import Gemini
from video import Editor
from caption import Handler
from youtube import Uploader
import re
from typing import List, Dict, Union, Optional, Callable, TypeVar, Any
from utils.colors import Colors

T = TypeVar("T")


class Orchestrator:
    """Coordinates video generation pipeline."""

    def __init__(
        self,
        preset: YmlHandler,
        scraper: Scraper,
        gemini: Gemini,
        editor: Editor,
        caption: Handler,
        uploader: Optional[Uploader],
    ) -> None:
        self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)
        self.preset: YmlHandler = preset
        self.scraper: Scraper = scraper
        self.gemini: Gemini = gemini
        self.editor: Editor = editor
        self.caption: Handler = caption
        self.uploader: Optional[Uploader] = uploader
        self.prompt: Prompt = Prompt()

    def _upload(
        self, data: Dict[str, str], video_path: Union[str, Path]
    ) -> Optional[str]:
        """
        Upload video to YouTube and track used content.

        Args:
            data: Video metadata dictionary.
            video_path: Path to video file.

        Returns:
            Optional[str]: YouTube video URL if successful, None otherwise.
        """
        if not self.uploader:
            return None
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
            video_url, scheduled_time = self.uploader.upload(video_data=upload_dict)
            if video_url and scheduled_time:
                self.preset.set("LAST_UPLOAD", scheduled_time)
            return video_url
        except ResumableUploadError:
            self.preset.set(
                "LIMIT_TIME", str(datetime.datetime.now(datetime.UTC).isoformat())
            )
            self.logger.warning("Upload limit reached")
            return None

        current: List[str] = self.preset.get("USED_CONTENT") or []
        if title and title not in current:
            current.append(title.strip())
            self.preset.set("USED_CONTENT", current[-100:])

    def _process_task(self, data: Dict[str, str]) -> Path:
        """
        Generate video assets and assemble final output.

        Args:
            data: Dictionary containing transcript, search_term, etc.

        Returns:
            Path: Path to assembled video file.
        """
        search_term = data.get("search_term", "")
        self.logger.debug(f"Searching for media: {search_term}")
        media_path = self.scraper.get_media(search_term)
        self.logger.debug("Media downloaded")

        transcript = data.get("transcript", "")
        self.logger.debug("Generating audio...")
        audio_path = self.gemini.get_audio(transcript=transcript)
        self.logger.debug("Audio generated")

        self.logger.debug("Creating captions...")
        ass_path = self.caption.get_captions(audio_path=audio_path)
        self.logger.debug("Captions created")

        self.logger.debug("Assembling video...")
        video_path = self.editor.assemble(
            ass_path=ass_path, audio_path=audio_path, media_path=media_path
        )
        self.logger.debug(f"Video assembled: {video_path}")

        return video_path

    async def _animate_loading(self, message: str, stop_event: asyncio.Event) -> None:
        """
        Animate loading dots while task runs.

        Args:
            message: Message to display with animation.
            stop_event: Event to signal when to stop animation.
        """
        dots = [".", "..", "..."]
        i = 0
        while not stop_event.is_set():
            dot = dots[i % len(dots)]
            print(
                f"\r{Colors.YELLOW}{message}{dot}{' ' * (3 - len(dot))}{Colors.RESET}",
                end="",
                flush=True,
            )
            i += 1
            try:
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                break

    async def _stop_loading_task(
        self, stop_event: asyncio.Event, loading_task: asyncio.Task[None]
    ) -> None:
        """
        Stop loading animation cleanly.

        Args:
            stop_event: Event to signal stop.
            loading_task: Task to cancel.
        """
        stop_event.set()
        loading_task.cancel()
        try:
            await loading_task
        except asyncio.CancelledError:
            pass

    async def _execute_with_loading(
        self, message: str, task: Callable[..., T], *args: object, **kwargs: object
    ) -> T:
        """
        Execute task with animated loading indicator.

        Args:
            message: Loading message to display.
            task: Callable to execute.
            *args: Positional arguments for task.
            **kwargs: Keyword arguments for task.

        Returns:
            T: Result of task execution.
        """
        stop_event = asyncio.Event()
        loading_task = asyncio.create_task(self._animate_loading(message, stop_event))

        try:
            loop = asyncio.get_event_loop()

            def run_task():
                return task(*args, **kwargs)

            result = await loop.run_in_executor(None, run_task)
            await self._stop_loading_task(stop_event, loading_task)
            print(
                f"\r{Colors.YELLOW}{message}{Colors.RESET} {Colors.GREEN}✓{Colors.RESET}   "
            )
            return result
        except Exception as e:
            await self._stop_loading_task(stop_event, loading_task)
            print(
                f"\r{Colors.YELLOW}{message}{Colors.RESET} {Colors.RED}✗{Colors.RESET}   "
            )
            self.logger.error(f"Failed {message.lower()}: {e}", exc_info=True)
            raise

    async def process(self, prompt: str) -> Path:
        """
        Process prompt through full video generation pipeline.

        Args:
            prompt: User topic/prompt string.

        Returns:
            Path: Path to generated video file.
        """
        response: str = self.prompt.build(prompt, self.preset.get("USED_CONTENT", []))

        stop_event = asyncio.Event()
        loading_task = asyncio.create_task(
            self._animate_loading("Generating content script", stop_event)
        )

        try:
            loop = asyncio.get_event_loop()
            text: str = await loop.run_in_executor(
                None, self.gemini.get_response, response, 2.5
            )
            await self._stop_loading_task(stop_event, loading_task)
            print(
                f"\r{Colors.YELLOW}Generating content script{Colors.RESET} {Colors.GREEN}✓{Colors.RESET}   "
            )
        except Exception as e:
            await self._stop_loading_task(stop_event, loading_task)
            print(
                f"\r{Colors.YELLOW}Generating content script{Colors.RESET} {Colors.RED}✗{Colors.RESET}   "
            )
            self.logger.error(f"Failed to generate content script: {e}", exc_info=True)
            raise

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
                print(
                    f"\n{Colors.RED}ERR Failed to extract transcript{Colors.RESET}"
                )
                raise ValueError(
                    "Cannot proceed without transcript. Gemini response did not contain "
                    "TRANSCRIPT: field and fallback extraction failed."
                )

        title = result.get("title", "N/A")
        print(
            f"{Colors.GREEN}OK{Colors.RESET} {Colors.WHITE}Generated Content:{Colors.RESET} {Colors.MAGENTA}{title}{Colors.RESET}\n"
        )

        transcript = result.get("transcript", "")
        search_term = result.get("search_term", "")

        audio_path = await self._execute_with_loading(
            "Generating voiceover", self.gemini.get_audio, transcript
        )
        print(
            f"{Colors.GREEN}OK{Colors.RESET} {Colors.WHITE}Voiceover path:{Colors.RESET} {Colors.MAGENTA}{audio_path}{Colors.RESET}\n"
        )

        ass_path = await self._execute_with_loading(
            "Generating captions", self.caption.get_captions, audio_path
        )
        print(
            f"{Colors.GREEN}OK{Colors.RESET} {Colors.WHITE}Captions path:{Colors.RESET} {Colors.MAGENTA}{ass_path}{Colors.RESET}\n"
        )

        media_path = await self._execute_with_loading(
            "Preparing background video", self.scraper.get_media, search_term
        )
        print(
            f"{Colors.GREEN}OK{Colors.RESET} {Colors.WHITE}Background video path:{Colors.RESET} {Colors.MAGENTA}{media_path}{Colors.RESET}\n"
        )

        video_path = await self._execute_with_loading(
            "Assembling video elements",
            self.editor.assemble,
            ass_path,
            audio_path,
            media_path,
        )

        print(
            f"{Colors.GREEN}OK{Colors.RESET} {Colors.WHITE}Output Path:{Colors.RESET} {Colors.MAGENTA}{video_path}{Colors.RESET}\n"
        )

        if self.uploader:
            stop_event = asyncio.Event()
            loading_task = asyncio.create_task(
                self._animate_loading("Uploading to YouTube", stop_event)
            )

            try:
                loop = asyncio.get_event_loop()
                video_url = await loop.run_in_executor(
                    None, self._upload, result, video_path
                )
                await self._stop_loading_task(stop_event, loading_task)
                if video_url:
                    print(
                        f"\r{Colors.YELLOW}Uploading to YouTube{Colors.RESET} {Colors.GREEN}✓{Colors.RESET}   "
                    )
                    print(
                        f"{Colors.GREEN}OK{Colors.RESET} {Colors.WHITE}Successfully uploaded short:{Colors.RESET} {Colors.MAGENTA}{video_url}{Colors.RESET}\n"
                    )
                else:
                    print(
                        f"\r{Colors.YELLOW}Uploading to YouTube{Colors.RESET} {Colors.RED}✗{Colors.RESET}   "
                    )
                    raise Exception("Upload returned no URL")
            except Exception as e:
                await self._stop_loading_task(stop_event, loading_task)
                print(
                    f"\r{Colors.YELLOW}Uploading to YouTube{Colors.RESET} {Colors.RED}✗{Colors.RESET}   "
                )
                self.logger.error(f"Failed to upload to YouTube: {e}", exc_info=True)
                raise

        await asyncio.sleep(0.01)
        return video_path
