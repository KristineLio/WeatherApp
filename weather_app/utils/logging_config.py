# weather_app/utils/logging_config.py
from __future__ import annotations

import logging
import os


def setup_logging() -> None:
    """
    Central logging setup.

    - Default INFO (clean for normal runs)
    - Set WEATHER_APP_LOG_LEVEL=DEBUG to get debug logs
    """
    level_name = os.getenv("WEATHER_APP_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    #Avoid duplicate handlers if setup_logging() is ever called twice. do nothing
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(level)
        return

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    # keep noisy libs quiet
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
