import datetime
from google import genai
from caption import Handler
from response import Gemini
from preset import YmlHandler
from youtube import Uploader
from media import Scraper
from video import Editor
from contextlib import contextmanager
import asyncio
import logging
import os
import shutil
import tempfile
from dotenv import load_dotenv
from pathlib import Path
from argparse import ArgumentParser
from orchastrator import Orchastrator

# -------------------------------
# Logging Configuration
# -------------------------------
logging.basicConfig(
    level=logging.DEBUG, format="%(levelname)s - %(message)s", force=True
)


# -------------------------------
# Temporary Workspace
# -------------------------------
@contextmanager
def new_workspace():
    temp_dir = tempfile.mkdtemp()
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir)


class Core:
    def __init__(self, workspace, path):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.workspace = Path(workspace)
        self.logger.info(workspace)

        self.preset = YmlHandler(Path(path))

        self.client = genai.Client(
            api_key=(
                self.preset.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
            )
        )

        self.scraper = Scraper(workspace=self.workspace)
        self.editor = Editor(workspace=self.workspace)
        self.gemini = Gemini(client=self.client, workspace=self.workspace)
        self.caption = Handler(
            workspace=self.workspace,
            model_size=self.preset.get("WHISPER_MODEL", default="small"),
            font=self.preset.get("FONT", default="Comic Sans MS"),
        )

        self.uploader = None
        if self.preset.get("UPLOAD") is not False:
            self.uploader = Uploader(
                name=self.preset.get("NAME", default="crank"),
                auth_token=self.preset.get("OAUTH_PATH", "secrets.json"),
            )

        self.orchastrator = Orchastrator(
            preset=self.preset,
            scraper=self.scraper,
            gemini=self.gemini,
            editor=self.editor,
            caption=self.caption,
            uploader=self.uploader,
        )

    def _time_left(self, num_hours=24):
        limit_time = self.preset.get("LIMIT_TIME")
        if not limit_time:
            return 0

        limit_time_dt = datetime.datetime.fromisoformat(limit_time)
        elapsed = datetime.datetime.now(datetime.UTC) - limit_time_dt
        hours = datetime.timedelta(hours=num_hours)

        return int(max((hours - elapsed).total_seconds(), 0))

    async def run(self):
        while True:
            try:
                if hasattr(self, "uploader"):
                    time_left = self._time_left(num_hours=24)
                    while time_left > 0:
                        hours, minutes, seconds = (
                            time_left // 3600,
                            (time_left % 3600) // 60,
                            time_left % 60,
                        )
                        print(
                            f"\r[{self.preset.get('NAME')}] Crank will continue in {hours}h {minutes}m {seconds}s",
                            end="",
                        )
                        await asyncio.sleep(1)
                        time_left -= 1

                prompt = self.preset.get("PROMPT")
                if not prompt:
                    prompt = input("Prompt -> ")

                await self.orchastrator.process(prompt)
                await asyncio.sleep(0.01)

            except RuntimeError as e:
                self.logger.critical(e)
                break
            except KeyboardInterrupt:
                self.logger.info("Shutting down...")
                break
            except Exception as e:
                self.logger.error(e)


if __name__ == "__main__":
    load_dotenv()

    parser = ArgumentParser()
    parser.add_argument("--path", help="Path to config.yml", default="preset.yml")
    args = parser.parse_args()
    path = args.path

    with new_workspace() as workspace:
        core = Core(workspace, path)
        asyncio.run(core.run())
