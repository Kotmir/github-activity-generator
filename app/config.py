"""Validated settings of one generation run."""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Optional

from .errors import ConfigError

MAX_COMMITS_LIMIT = 20
MAX_DAYS_BEFORE = 3650
MAX_DAYS_AFTER = 365
MAX_TOTAL_DAYS = 3660
MODES = ('file', 'empty')

_REMOTE_RE = re.compile(
    r'^(?:https?://|ssh://|git://)[^\s]+$|^[\w.\-]+@[\w.\-]+:[^\s]+$')
_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
_CONTROL_RE = re.compile(r'[\x00-\x1f\x7f]')
_USERINFO_RE = re.compile(r'(?<=//)[^/\s@]+@')


def mask_secrets(text):
    """Hide `user:token@` parts of URLs before they reach the logs."""
    return _USERINFO_RE.sub('***@', text or '')


def _int(data, field, default, low, high):
    value = data.get(field)
    if value is None or value == '':
        return default
    if isinstance(value, bool):
        raise ConfigError('err.type', field)
    try:
        number = int(value)
        if isinstance(value, float) and number != value:
            raise ValueError
    except (TypeError, ValueError):
        raise ConfigError('err.type', field)
    if not low <= number <= high:
        raise ConfigError('err.range', field, min=low, max=high)
    return number


def _text(data, field, limit=200):
    value = data.get(field)
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    if (len(value) > limit or _CONTROL_RE.search(value)
            or value.startswith('-')):
        raise ConfigError('err.invalid', field)
    return value


@dataclass
class Config:
    repository: Optional[str] = None
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    days_before: int = 365
    days_after: int = 0
    frequency: int = 80
    max_commits: int = 10
    no_weekends: bool = False
    mode: str = 'file'
    seed: Optional[int] = None
    output_dir: str = 'output'

    @classmethod
    def from_dict(cls, data):
        """Build a Config from untrusted input (JSON body / CLI)."""
        if not isinstance(data, dict):
            raise ConfigError('err.invalid', 'config')
        cfg = cls(
            repository=_text(data, 'repository', 500),
            user_name=_text(data, 'user_name'),
            user_email=_text(data, 'user_email'),
            days_before=_int(data, 'days_before', 365, 0, MAX_DAYS_BEFORE),
            days_after=_int(data, 'days_after', 0, 0, MAX_DAYS_AFTER),
            frequency=_int(data, 'frequency', 80, 0, 100),
            max_commits=_int(data, 'max_commits', 10, 1,
                             MAX_COMMITS_LIMIT),
            no_weekends=bool(data.get('no_weekends', False)),
            mode=str(data.get('mode') or 'file'),
            seed=_int(data, 'seed', None, 0, 2 ** 63 - 1),
            output_dir=str(data.get('output_dir') or 'output').strip(),
        )
        cfg.validate()
        return cfg

    def validate(self):
        if self.repository and not _REMOTE_RE.match(self.repository):
            raise ConfigError('err.repository', 'repository')
        if self.user_email and not _EMAIL_RE.match(self.user_email):
            raise ConfigError('err.email', 'user_email')
        if self.mode not in MODES:
            raise ConfigError('err.mode', 'mode')
        if (not self.output_dir or len(self.output_dir) > 260
                or _CONTROL_RE.search(self.output_dir)):
            raise ConfigError('err.output', 'output_dir')
        if self.days_before + self.days_after > MAX_TOTAL_DAYS:
            raise ConfigError('err.total_days', 'days_before',
                              max=MAX_TOTAL_DAYS)

    def to_dict(self):
        return asdict(self)
