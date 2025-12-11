import sys
import asyncio
from pathlib import Path
from src.core.app import new_workspace, Core
import subprocess
from typing import List
import traceback

CONFIG_DIR = Path(".configs")


def run_core(config_path: str) -> None:
    """
    Run core application with specified config.

    Args:
        config_path: Path to configuration file.
    """
    try:
        with new_workspace() as workspace:
            core = Core(workspace, config_path)
            asyncio.run(core.run())
    except Exception as e:
        print(f"\n{'='*60}", file=sys.stderr)
        print(f"ERROR in run_core with config: {config_path}", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)
        print(f"\nPress Enter to close...", file=sys.stderr)
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            pass
        sys.exit(1)


def launch_in_term(config_path: Path) -> None:
    """
    Launch application in new terminal.

    Args:
        config_path: Path to configuration file.
    """
    TERMINAL_CMD: str = "kitty"
    script_path = Path(__file__).resolve()
    uv_python = subprocess.run(["which", "uv"], capture_output=True, text=True)
    if uv_python.returncode == 0:
        python_cmd = ["uv", "run", "python", str(script_path), str(config_path)]
    else:
        python_cmd = ["python3", str(script_path), str(config_path)]
    
    cmd = [
        TERMINAL_CMD,
        "--hold",
        "--",
    ] + python_cmd
    
    print(f"Launching {config_path.name} in new terminal...", file=sys.stderr)
    subprocess.Popen(cmd)


def main() -> None:
    try:
        if len(sys.argv) > 1:
            run_core(sys.argv[1])
            return

        CONFIG_PATHS: List[Path] = list(CONFIG_DIR.glob("*.yml"))
        if not CONFIG_PATHS:
            print(f"ERROR: No config files found in {CONFIG_DIR}", file=sys.stderr)
            print(f"Please create config files in {CONFIG_DIR.absolute()} or provide a config path as argument.", file=sys.stderr)
            sys.exit(1)
        
        if len(CONFIG_PATHS) == 1:
            run_core(str(CONFIG_PATHS[0]))
        else:
            print(f"Found {len(CONFIG_PATHS)} config files, launching each in separate terminal...", file=sys.stderr)
            for config_path in CONFIG_PATHS:
                launch_in_term(config_path)
    except Exception as e:
        print(f"\n{'='*60}", file=sys.stderr)
        print(f"ERROR in main()", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        print(f"{'='*60}\n", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
