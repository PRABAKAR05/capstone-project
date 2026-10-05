"""
CSCM-IoMT Structured Logging
=============================
Provides a consistent logger factory that writes to both console
and rotating file handlers.

Usage::

    from src.utils.logging import get_logger

    logger = get_logger(__name__)
    logger.info("Audit started")
    logger.warning("Missing file: %s", path)
    logger.error("Failed to parse record %s", record_id)

"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional


# -----------------------------------------------------------------------
# Internal state
# -----------------------------------------------------------------------
_INITIALIZED: bool = False
_LOG_FILE: Optional[Path] = None


# -----------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------

def setup_logging(
    log_dir: Optional[Path] = None,
    log_filename: str = "cscm_iomt.log",
    level: int = logging.INFO,
    console: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 3,
) -> None:
    """
    Configure the root logger once for the entire application.

    Subsequent calls to get_logger() will inherit these settings.

    Parameters
    ----------
    log_dir : Path, optional
        Directory for log files. If None, only console logging is used.
    log_filename : str
        Name of the rotating log file.
    level : int
        Logging level (e.g., logging.DEBUG, logging.INFO).
    console : bool
        Whether to attach a StreamHandler to stderr.
    max_bytes : int
        Maximum size of each log file before rotation.
    backup_count : int
        Number of rotated log files to keep.
    """
    global _INITIALIZED, _LOG_FILE

    root = logging.getLogger()
    if _INITIALIZED:
        return  # Already set up — do not duplicate handlers

    root.setLevel(level)

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    if console:
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(level)
        ch.setFormatter(fmt)
        root.addHandler(ch)

    # File handler
    if log_dir is not None:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / log_filename
        fh = RotatingFileHandler(
            log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        fh.setLevel(level)
        fh.setFormatter(fmt)
        root.addHandler(fh)
        _LOG_FILE = log_path

    _INITIALIZED = True


def get_logger(name: str, level: int = logging.DEBUG) -> logging.Logger:
    """
    Get a named logger.

    If setup_logging() has not been called yet, calls it with defaults
    (console only, INFO level).

    Parameters
    ----------
    name : str
        Logger name — typically __name__ of the calling module.
    level : int
        Per-logger level override.

    Returns
    -------
    logging.Logger
    """
    if not _INITIALIZED:
        setup_logging()
    logger = logging.getLogger(name)
    logger.setLevel(level)
    return logger


def get_log_file() -> Optional[Path]:
    """Return the current log file path, or None if file logging is disabled."""
    return _LOG_FILE


def reset_logging() -> None:
    """
    Reset logging state (used in tests only).

    .. warning::
        This removes all handlers from the root logger.
        Do NOT call in production code.
    """
    global _INITIALIZED, _LOG_FILE
    root = logging.getLogger()
    for handler in root.handlers[:]:
        handler.close()
        root.removeHandler(handler)
    _INITIALIZED = False
    _LOG_FILE = None
