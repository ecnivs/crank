import logging
import queue
import datetime
from googleapiclient.http import ResumableUploadError
import asyncio
from prompt import Prompt


class Orchastrator:
    def __init__(self, preset, scraper, gemini, editor, caption, uploader):
        self.logger = logging.getLogger(__class__.__name__)

        self.queue = queue.Queue()

        self.preset = preset
        self.scraper = scraper
        self.gemini = gemini
        self.editor = editor
        self.caption = caption
        self.uploader = uploader
        self.prompt = Prompt()

    def _upload(self, data, output_path):
        title = data.get("title", "crank short")

        upload_dict = {
            "video_path": output_path,
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

        current = self.preset.get("USED_CONTENT") or []
        if title and title not in current:
            current.append(title.strip())
            self.preset.set("USED_CONTENT", current[-100:])

    def _process_task(self, data):
        media_path = self.scraper.get_media(data.get("search_term"))
        logging.info(f"Template: {media_path}")

        audio_path = self.gemini.get_audio(transcript=data.get("content"))
        logging.info(f"Voiceover: {audio_path}")

        ass_path = self.caption.get_captions(audio_path=audio_path)
        logging.info(f"Captions: {ass_path}")

        output_path = self.editor.assemble(
            ass_path=ass_path, audio_path=audio_path, media_path=media_path
        )

        if self.uploader:
            self._upload(data, output_path)

    async def process(self, prompt):
        self.logger.info(f"New Prompt: {prompt}")
        response = self.prompt.build(prompt)

        text = self.gemini.get_response(response, 2.5)

        for line in text.splitlines():
            if line.startswith("TRANSCRIPT:"):
                transcript = line[len("TRANSCRIPT:") :].strip()
            elif line.startswith("DESCRIPTION:"):
                description = line[len("DESCRIPTION:") :].strip()
            elif line.startswith("SEARCH_TERM:"):
                search_term = line[len("SEARCH_TERM:") :].strip()
            elif line.startswith("TITLE:"):
                title = line[len("TITLE:") :].strip()
            elif line.startswith("CATEGORY_ID:"):
                categoryId = line[len("CATEGORY_ID:") :].strip()

        self._process_task(
            {
                "search_term": search_term,
                "content": transcript,
                "title": title,
                "categoryId": categoryId,
                "description": description,
            }
        )

        await asyncio.sleep(0.01)
