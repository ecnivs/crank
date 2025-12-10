import datetime
from contextlib import contextmanager
from typing import Generator, Optional
import asyncio
import logging
from logging.handlers import RotatingFileHandler
import os
import re
import shutil
import sys
import tempfile
import tomllib
from argparse import ArgumentParser
from pathlib import Path
from dotenv import load_dotenv


from utils.colors import Colors
from utils.constants import (
    DEFAULT_CHANNEL_NAME,
    DEFAULT_FONT,
    DEFAULT_WHISPER_MODEL,
    DEFAULT_SECRETS_FILE,
    DEFAULT_PRESET_FILE,
)


def setup_logging(log_file: Path = Path("logs/crank.log")) -> None:
    """
    Configure logging to file (with rotation) and console.

    Args:
        log_file: Path to log file.
    """
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    root_logger.setLevel(logging.DEBUG)

    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_file, encoding="utf-8", maxBytes=10 * 1024 * 1024, backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter("%(message)s")
    console_handler.setFormatter(console_formatter)

    class ConsoleFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            important_modules = ["Core", "Orchestrator"]
            if record.name in important_modules:
                if record.levelno >= logging.INFO:
                    return True
            return False

    console_handler.addFilter(ConsoleFilter())

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


from preset import YmlHandler


def get_channel_name_from_preset(path: str) -> str:
    """
    Read channel name from preset file.

    Args:
        path: Path to preset YAML file.

    Returns:
        str: Channel name or default channel name.
    """
    try:
        preset_path = Path(path)
        if not preset_path.exists():
            print(
                f"{Colors.YELLOW}Warning: Preset file {path} does not exist, using default channel name{Colors.RESET}"
            )
            return DEFAULT_CHANNEL_NAME
        preset = YmlHandler(preset_path)
        channel_name = preset.get("NAME")

        if channel_name is None:
            print(
                f"\n{Colors.YELLOW}Warning: No 'NAME' field found in preset file '{path}'. Using default channel name '{DEFAULT_CHANNEL_NAME}'.{Colors.RESET}\n"
            )
            return DEFAULT_CHANNEL_NAME

        channel_name_str = str(channel_name).strip()
        if not channel_name_str:
            print(
                f"\n{Colors.YELLOW}Warning: 'NAME' field in preset file '{path}' is empty. Using default channel name '{DEFAULT_CHANNEL_NAME}'.{Colors.RESET}\n"
            )
            return DEFAULT_CHANNEL_NAME

        return channel_name_str
    except Exception as e:
        print(
            f"{Colors.YELLOW}Warning: Failed to read channel name from {path}: {e}. Using default.{Colors.RESET}"
        )
        return DEFAULT_CHANNEL_NAME


from google import genai
from caption import Handler
from response import Gemini, QuotaExceededError
from youtube import Uploader
from media import Scraper
from video import Editor
from orchestrator import Orchestrator


@contextmanager
def new_workspace() -> Generator[str, None, None]:
    """
    Create temporary workspace directory.

    Yields:
        str: Path to temporary directory.
    """
    temp_dir = tempfile.mkdtemp()
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir)


def get_version() -> str:
    """
    Get version from pyproject.toml.

    Returns:
        str: Version string from pyproject.toml.
    """
    pyproject_path = Path(__file__).parent / "pyproject.toml"
    try:
        with open(pyproject_path, "rb") as f:
            pyproject = tomllib.load(f)
            return pyproject["project"]["version"]
    except (FileNotFoundError, KeyError, Exception):
        return "0.2.0"


def print_banner() -> None:
    """Print application banner."""
    version = get_version()
    banner = f"""{Colors.CYAN}
 ██████╗██████╗  █████╗ ███╗   ██╗██╗  ██╗
██╔════╝██╔══██╗██╔══██╗████╗  ██║██║ ██╔╝
██║     ██████╔╝███████║██╔██╗ ██║█████╔╝ 
██║     ██╔══██╗██╔══██║██║╚██╗██║██╔═██╗ 
╚██████╗██║  ██║██║  ██║██║ ╚████║██║  ██╗
 ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝{Colors.RESET}
    by ecnivs ~ automate your shorts :3
                v{version}
    """
    print(banner)


class Core:
    """Main application controller."""

    def __init__(self, workspace: str, path: str) -> None:
        self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)
        self.is_running: bool = True

        self.workspace: Path = Path(workspace)
        self.logger.debug(f"Temporary workspace: {workspace}")

        self.preset_path: str = path
        self.preset: YmlHandler = YmlHandler(Path(self.preset_path))
        self.channel_name = self.preset.get("NAME", DEFAULT_CHANNEL_NAME)
        api_key = self.preset.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY not found. Please set it in preset.yml or .env file. "
                "Get your API key from: https://makersuite.google.com/app/apikey"
            )
        self.client: genai.Client = genai.Client(api_key=api_key)

        self.uploader: Optional[Uploader] = None
        if self.preset.get("UPLOAD") is not False:
            self.uploader = Uploader(
                name=self.preset.get("NAME", DEFAULT_CHANNEL_NAME),
                auth_token=self.preset.get("OAUTH_PATH", str(DEFAULT_SECRETS_FILE)),
            )

        self.orchestrator: Orchestrator = Orchestrator(
            preset=self.preset,
            scraper=Scraper(workspace=self.workspace),
            gemini=Gemini(client=self.client, workspace=self.workspace),
            editor=Editor(workspace=self.workspace),
            caption=Handler(
                workspace=self.workspace,
                model_size=self.preset.get("WHISPER_MODEL", DEFAULT_WHISPER_MODEL),
                font=self.preset.get("FONT", DEFAULT_FONT),
            ),
            uploader=self.uploader,
        )

    def _time_left(self, num_hours: int = 24) -> int:
        """
        Calculate remaining cooldown time in seconds.

        Args:
            num_hours: Cooldown period in hours.

        Returns:
            int: Remaining seconds until cooldown expires.
        """
        limit_time = self.preset.get("LIMIT_TIME")
        if not limit_time:
            return 0

        limit_time_dt = datetime.datetime.fromisoformat(limit_time)
        elapsed = datetime.datetime.now(datetime.UTC) - limit_time_dt
        hours = datetime.timedelta(hours=num_hours)

        return int(max((hours - elapsed).total_seconds(), 0))

    async def run(self) -> None:
        """Main application loop for processing prompts."""
        print_banner()

        while self.is_running:
            try:
                time_left = self._time_left(num_hours=24)
                if time_left > 0:
                    print(
                        f"\n{Colors.YELLOW}Rate limit cooldown active...{Colors.RESET}"
                    )
                    while time_left > 0:
                        hours, minutes, seconds = (
                            time_left // 3600,
                            (time_left % 3600) // 60,
                            time_left % 60,
                        )
                        print(
                            f"\r{Colors.DIM}Waiting: {hours:02d}h {minutes:02d}m {seconds:02d}s remaining{Colors.RESET}",
                            end="",
                            flush=True,
                        )
                        await asyncio.sleep(1)
                        time_left -= 1
                    print("\n")

                prompt: Optional[str] = self.preset.get("PROMPT")
                if prompt:
                    print(
                        f"\n{Colors.WHITE}({self.channel_name}) >>>{Colors.RESET} {Colors.YELLOW}Prompt imported from {self.preset_path}{Colors.RESET}"
                    )
                    print()
                else:
                    prompt = input(
                        f"\n{Colors.WHITE}({self.channel_name}) >>>{Colors.RESET} "
                    ).strip()
                    if not prompt:
                        print(
                            f"{Colors.YELLOW}No prompt provided, skipping...{Colors.RESET}"
                        )
                        continue
                    print()

                await self.orchestrator.process(prompt)

            except QuotaExceededError:
                continue
            except RuntimeError as e:
                self.logger.critical(f"Runtime error: {e}", exc_info=True)
                print(f"\n{Colors.RED}ERR {e}{Colors.RESET}\n")
                self.is_running = False
                return
            except KeyboardInterrupt:
                self.is_running = False
                print()
                raise
            except Exception as e:
                self.logger.error(f"Error during processing: {e}", exc_info=True)
                print(f"\n{Colors.RED}ERR {e}{Colors.RESET}\n")
                await asyncio.sleep(1)


if __name__ == "__main__":
    load_dotenv()

    parser = ArgumentParser(description="Crank - Automated YouTube Shorts Generator")
    parser.add_argument(
        "--path",
        help="Path to config.yml (overrides PRESET_PATH env var)",
        default=None,
        type=str,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {get_version()}",
    )
    args = parser.parse_args()
    path: str = args.path or os.environ.get("PRESET_PATH", str(DEFAULT_PRESET_FILE))

    preset_path = Path(path)
    if not preset_path.exists():
        print(
            f"{Colors.RED}Error: Preset file not found: {path}{Colors.RESET}\n"
            f"{Colors.YELLOW}Please create a {DEFAULT_PRESET_FILE} file or specify a valid path with --path{Colors.RESET}\n"
        )
        sys.exit(1)

    channel_name = get_channel_name_from_preset(path)

    sanitized_name = re.sub(r"[^\w\-_\.]", "_", channel_name)
    if sanitized_name != channel_name:
        print(
            f"{Colors.YELLOW}Warning: Channel name '{channel_name}' contains invalid filename characters. Using '{sanitized_name}' for log file.{Colors.RESET}"
        )
        channel_name = sanitized_name

    log_file = Path("logs") / f"{channel_name}.log"

    print(f"{Colors.DIM}Logging to: {log_file.absolute()}{Colors.RESET}\n")

    setup_logging(log_file)

    try:
        with new_workspace() as workspace:
            core = Core(workspace, path)
            asyncio.run(core.run())
    except KeyboardInterrupt:
        print(
            f"\n{Colors.GREEN}OK{Colors.RESET} {Colors.WHITE}Exiting cleanly...{Colors.RESET}\n"
        )
        logging.info("Interrupted by user. Exiting cleanly...")
        sys.exit(0)
    except SystemExit:
        raise
    except QuotaExceededError:
        sys.exit(0)
    except Exception as e:
        logging.critical(f"Fatal Error: {e}", exc_info=True)
        print(f"\n{Colors.RED}ERR {e}{Colors.RESET}\n")
        sys.exit(1)
