"""
Unified logging for pt-claw scripts.

Provides:
  - RotatingFileHandler (10 MB × 5 backups = 50 MB cap)
  - Per-invocation call_id for tracing request chains
  - Structured log format: timestamp | call_id | level | script | message

Usage in scripts:
    from _logger import get_logger
    log = get_logger("pt_search")
    log.info("searching site=%s query=%s", site, query)
    log.error("HTTP %d from %s", status, url)
"""
import logging
import os
import sys
import uuid
from logging.handlers import RotatingFileHandler

_skill_dir = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(_skill_dir, "..", "logs")
LOG_FILE = os.path.join(LOG_DIR, "pt-claw.log")

_MAX_BYTES = 10 * 1024 * 1024   # 10 MB per file
_BACKUP_COUNT = 5                # 5 rotated backups
_TOTAL_CAP_MB = _MAX_BYTES * (_BACKUP_COUNT + 1) // (1024 * 1024)

_call_id = uuid.uuid4().hex[:8]

_formatter = logging.Formatter(
    fmt="%(asctime)s.%(msecs)03d | %(call_id)s | %(levelname)-5s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    defaults={"call_id": _call_id},
)


class _CallIdFilter(logging.Filter):
    def filter(self, record):
        record.call_id = getattr(record, "call_id", _call_id)
        return True


_handler = None


def _ensure_handler():
    global _handler
    if _handler is not None:
        return
    os.makedirs(LOG_DIR, exist_ok=True)
    _handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    _handler.setFormatter(_formatter)
    _handler.addFilter(_CallIdFilter())


def get_logger(name: str = "pt-claw") -> logging.Logger:
    _ensure_handler()
    logger = logging.getLogger(f"pt-claw.{name}")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(_handler)
    logger.propagate = False
    return logger
