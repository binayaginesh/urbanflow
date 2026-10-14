"""
logging_setup.py – Configure structured logging for the pipeline.

Call ``setup_logging()`` once at CLI startup.  All modules then use
``logging.getLogger(__name__)`` and inherit this configuration.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

try:
    import colorlog
    _HAS_COLORLOG = True
except ImportError:
    _HAS_COLORLOG = False


def setup_logging(
    cfg: dict[str, Any] | None = None,
    *,
    level: str | None = None,
    log_file: str | Path | None = None,
) -> None:
    """
    Set up root logger.

    Parameters
    ----------
    cfg:
        Parsed config dict (uses cfg["logging"]["level"] / cfg["logging"]["log_file"]).
    level:
        Override log level string (e.g. "DEBUG").
    log_file:
        Override log file path.  Pass ``""`` to disable file logging.
    """
    log_cfg = (cfg or {}).get("logging", {})
    effective_level = (level or log_cfg.get("level", "INFO")).upper()
    effective_file = log_file if log_file is not None else log_cfg.get("log_file", "")

    root = logging.getLogger()
    root.setLevel(effective_level)
    root.handlers.clear()

    # Console handler
    if _HAS_COLORLOG:
        fmt = (
            "%(log_color)s%(asctime)s [%(levelname)-8s]%(reset)s "
            "%(name)s – %(message)s"
        )
        ch = colorlog.StreamHandler(sys.stdout)
        ch.setFormatter(
            colorlog.ColoredFormatter(
                fmt,
                datefmt="%H:%M:%S",
                log_colors={
                    "DEBUG":   "cyan",
                    "INFO":    "green",
                    "WARNING": "yellow",
                    "ERROR":   "red",
                    "CRITICAL": "bold_red",
                },
            )
        )
    else:
        fmt = "%(asctime)s [%(levelname)-8s] %(name)s – %(message)s"
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(logging.Formatter(fmt, datefmt="%H:%M:%S"))

    root.addHandler(ch)

    # File handler (optional)
    if effective_file:
        fh = logging.FileHandler(effective_file, encoding="utf-8")
        fh.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)-8s] %(name)s – %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        root.addHandler(fh)

    logging.getLogger(__name__).debug("Logging initialised at level %s", effective_level)
