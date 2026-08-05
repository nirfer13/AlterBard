"""Central logging setup for the bot.

Console output disappears the moment the window is closed, which is exactly
when it is needed - the YouTube outages this bot suffers from show up hours
after the fact. Everything therefore also goes to a rotating file in logs/,
next to Lavalink's own spring.log.

The module is deliberately named bot_logging and not logging, so it cannot
shadow the standard library module.
"""

import logging
import logging.handlers
import sys
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_FILE = LOG_DIR / "bot.log"

# Keep two weeks of daily files: enough to look back at a weekend outage
# without letting the folder grow without bound.
BACKUP_DAYS = 14

# File lines carry the source location, because the useful question after a
# failure is always "which branch produced this".
FILE_FORMAT = "%(asctime)s %(levelname)-8s %(name)s %(filename)s:%(lineno)d | %(message)s"
CONSOLE_FORMAT = "%(asctime)s %(levelname)-8s %(message)s"
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def _console_handler() -> logging.StreamHandler:
    """Build the console handler, forcing UTF-8 where Windows allows it."""

    # Without this the Polish characters in track titles come out as mojibake
    # on a Windows console using the legacy code page.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(CONSOLE_FORMAT, TIME_FORMAT))
    return handler


def _file_handler() -> logging.Handler:
    """Build the rotating file handler."""

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    handler = logging.handlers.TimedRotatingFileHandler(
        LOG_FILE,
        when="midnight",
        backupCount=BACKUP_DAYS,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(FILE_FORMAT, TIME_FORMAT))
    return handler


def setup_logging(debug: bool = False) -> None:
    """Send the bot's logs to both the console and logs/bot.log.

    Call once, before the bot starts. Pass debug=True to also capture
    wavelink's internal chatter, which is what shows whether a voice update
    reached Lavalink at all.
    """

    level = logging.DEBUG if debug else logging.INFO

    root = logging.getLogger()
    root.setLevel(level)

    # Re-running setup (e.g. after a reload) must not double every line.
    for existing in root.handlers[:]:
        root.removeHandler(existing)
        existing.close()

    root.addHandler(_console_handler())
    root.addHandler(_file_handler())

    # discord.py's DEBUG level dumps every gateway payload, which buries
    # everything else. INFO already reports connects, resumes and disconnects.
    logging.getLogger("discord").setLevel(logging.INFO)
    # The voice client is the exception: when the bot silently drops out of the
    # channel, its DEBUG lines are the only record of why.
    logging.getLogger("discord.voice_client").setLevel(level)
    logging.getLogger("discord.gateway").setLevel(logging.INFO)

    # Wavelink logs the voice-update dispatch and node reconnects here.
    logging.getLogger("wavelink").setLevel(level)

    _install_exception_hooks()

    logging.getLogger(__name__).info("Logging started. File: %s", LOG_FILE)


def _install_exception_hooks() -> None:
    """Make sure a crash reaches the log file instead of only the console."""

    def handle_exception(exc_type, exc_value, exc_traceback):
        # Ctrl+C is a deliberate stop, not a failure worth a traceback.
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logging.getLogger("bot").critical(
            "Unhandled exception - the bot stopped.",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    sys.excepthook = handle_exception
