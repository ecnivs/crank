"""Utility classes and functions for the default plugin."""

import logging


class NullLogger:
    """Null logger to suppress yt-dlp output."""

    def debug(self, msg: object) -> None:
        pass

    def info(self, msg: object) -> None:
        pass

    def warning(self, msg: object) -> None:
        pass

    def error(self, msg: object) -> None:
        pass

    def critical(self, msg: object) -> None:
        pass

    def isEnabledFor(self, level: int) -> bool:
        return False


yt_dlp_logger = logging.getLogger("yt_dlp")
yt_dlp_logger.setLevel(logging.CRITICAL)
yt_dlp_logger.disabled = True
