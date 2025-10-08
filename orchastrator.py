import logging
import queue
import datetime
from googleapiclient.http import ResumableUploadError
import asyncio


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

    def _upload(self, data, output_path):
        title = data.get("title", "crank short")

        upload_dict = {
            "video_path": output_path,
            "title": title,
            "tags": data.get("tags", []),
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

    async def run(self):
        while True:
            if not self.queue.empty():
                data = self.queue.get()

                media_path = self.scraper.get_media(data.get("search_term"))
                audio_path = self.gemini.get_audio(transcript=data.get("content"))
                ass_path = self.caption.get_captions(audio_path=audio_path)

                output_path = self.editor.assemble(
                    ass_path=ass_path, audio_path=audio_path, media_path=media_path
                )

                if self.uploader:
                    self._upload(data, output_path)

            await asyncio.sleep(0.01)
