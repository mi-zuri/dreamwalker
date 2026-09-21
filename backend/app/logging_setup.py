"""Making the application's own logs visible.

Uvicorn configures its own loggers and leaves the root logger at WARNING, so
everything this app logs at INFO - which stage a game is on, what it cost, why
music fell back to loops - is dropped by default. That is fine until the first
time something goes wrong in a place with no debugger.

Cloud Run reads stdout, so that is where it goes.
"""

import logging
import sys

from app.settings import settings

FORMAT = "%(levelname)s %(name)s: %(message)s"


def configure() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(FORMAT))
        root.addHandler(handler)
    root.setLevel(level)

    # These two are conversational to the point of uselessness at INFO.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("google_genai.live_music").setLevel(logging.WARNING)
