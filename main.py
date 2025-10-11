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
from orchestrator import Orchestrator
from typing import Optional

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
    """
    Context manager that creates a temporary directory and cleans it up afterward.
    """
    temp_dir = tempfile.mkdtemp()
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir)


class Core:
    """
    Main class that wires together the entire pipeline.
    """

    def __init__(self, workspace: str, path: str) -> None:
        """
        Initialize all modules and orchestrator.

        Args:
            workspace: Path to temporary workspace.
            path: Path to YAML configuration file.
        """
        self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)
        self.workspace: Path = Path(workspace)
        self.logger.info(f"Temporary workspace: {workspace}")

        self.preset: YmlHandler = YmlHandler(Path(path))
        self.client: genai.Client = genai.Client(
            api_key=(
                self.preset.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
            )
        )

        self.uploader: Optional[Uploader] = None
        if self.preset.get("UPLOAD") is not False:
            self.uploader = Uploader(
                name=self.preset.get("NAME", default="crank"),
                auth_token=self.preset.get("OAUTH_PATH", "secrets.json"),
            )

        self.orchestrator: Orchestrator = Orchestrator(
            preset=self.preset,
            scraper=Scraper(workspace=self.workspace),
            gemini=Gemini(client=self.client, workspace=self.workspace),
            editor=Editor(workspace=self.workspace),
            caption=Handler(
                workspace=self.workspace,
                model_size=self.preset.get("WHISPER_MODEL", default="small"),
                font=self.preset.get("FONT", default="Comic Sans MS"),
            ),
            uploader=self.uploader,
        )

    def _time_left(self, num_hours: int = 24) -> int:
        """
        Calculate remaining cooldown time until next upload.

        Args:
            num_hours: Cooldown period in hours.

        Returns:
            int: Seconds remaining until next upload. Zero if ready.
        """
        limit_time = self.preset.get("LIMIT_TIME")
        if not limit_time:
            return 0

        limit_time_dt = datetime.datetime.fromisoformat(limit_time)
        elapsed = datetime.datetime.now(datetime.UTC) - limit_time_dt
        hours = datetime.timedelta(hours=num_hours)

        return int(max((hours - elapsed).total_seconds(), 0))

    async def run(self) -> None:
        """
        Main loop: continuously generate and upload videos based on prompts.
        """
        while True:
            try:
                if self.uploader:
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

                prompt: Optional[str] = self.preset.get("PROMPT")
                if not prompt:
                    prompt = input("Prompt -> ")

                await self.orchestrator.process(prompt)
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
    path: str = args.path

    with new_workspace() as workspace:
        core = Core(workspace, path)
        asyncio.run(core.run())
