"""Logging: rotating log file + console + an in-memory event list that the
web UI polls. Events keep a translation key, so the UI can switch language
on the fly and still show the whole history in the new language."""
from __future__ import annotations

import logging
import logging.handlers
import sys
import threading
import time
from pathlib import Path

from .errors import Cancelled
from .i18n import t, normalize_lang

LOGGER_NAME = 'gag'
LOG_FILE_NAME = 'activity-generator.log'
LIME = '\x1b[38;5;154m'
RESET = '\x1b[0m'
_PY_LEVELS = {'debug': logging.DEBUG, 'info': logging.INFO,
              'success': logging.INFO, 'warning': logging.WARNING,
              'error': logging.ERROR}


class _ColorFormatter(logging.Formatter):
    COLORS = {logging.DEBUG: '\x1b[90m', logging.INFO: LIME,
              logging.WARNING: '\x1b[33m', logging.ERROR: '\x1b[31m'}

    def format(self, record):
        text = super().format(record)
        return '%s%s%s' % (self.COLORS.get(record.levelno, ''), text, RESET)


def reset_logging():
    """Detach all handlers (used by tests and re-configuration)."""
    logger = logging.getLogger(LOGGER_NAME)
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
    logger._gag_ready = False


def setup_logging(log_dir, console=True):
    """Configure the 'gag' logger once; returns it."""
    logger = logging.getLogger(LOGGER_NAME)
    if getattr(logger, '_gag_ready', False):
        return logger
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / LOG_FILE_NAME, maxBytes=1_000_000, backupCount=5,
        encoding='utf-8')
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s | %(levelname)-7s | %(message)s'))
    logger.addHandler(file_handler)
    if console:
        stream = logging.StreamHandler(sys.stdout)
        stream.setLevel(logging.INFO)
        fmt = '%(asctime)s | %(message)s'
        if sys.stdout.isatty():
            stream.setFormatter(_ColorFormatter(fmt, '%H:%M:%S'))
        else:
            stream.setFormatter(logging.Formatter(fmt, '%H:%M:%S'))
        logger.addHandler(stream)
    logger._gag_ready = True
    return logger


class Reporter:
    """Collects events of one job and mirrors them to the logger."""

    def __init__(self, lang='ru'):
        self.lang = normalize_lang(lang)
        self.cancel_event = threading.Event()
        self._events = []
        self._lock = threading.Lock()
        self.done = 0
        self.total = 0
        self._logger = logging.getLogger(LOGGER_NAME)

    def log(self, level, key, **params):
        """level: debug | info | success | warning | error.
        `debug` goes to the log file only, the rest also to the UI."""
        self._logger.log(_PY_LEVELS[level], t(self.lang, key, **params))
        if level == 'debug':
            return
        with self._lock:
            self._events.append({'ts': time.time(), 'level': level,
                                 'key': key, 'params': params})

    def progress(self, done, total):
        self.done, self.total = done, total

    def cancel(self):
        self.cancel_event.set()

    def check_cancelled(self):
        if self.cancel_event.is_set():
            raise Cancelled()

    def events_since(self, index, lang=None):
        """Return (translated events after `index`, next index)."""
        lang = normalize_lang(lang or self.lang)
        with self._lock:
            chunk = self._events[index:]
            nxt = len(self._events)
        return [{'ts': e['ts'], 'level': e['level'],
                 'text': t(lang, e['key'], **e['params'])}
                for e in chunk], nxt
