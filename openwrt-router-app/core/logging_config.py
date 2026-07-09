from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from core.constants import LOGS_DIR

_LOG_FILE = LOGS_DIR / "app.log"
_configured = False


def configure_logging(level: int = logging.INFO) -> None:
    """Configure a rotating file handler for the whole app. Idempotent.

    Streamlit reruns the entrypoint script on every interaction, so this
    guards against attaching duplicate handlers on each rerun.
    """
    global _configured
    if _configured:
        return

    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    file_handler = RotatingFileHandler(_LOG_FILE, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(file_handler)

    _configured = True
