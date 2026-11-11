"""Errors that carry a translation key instead of a hard-coded text."""
from __future__ import annotations


class AppError(Exception):
    """Base error: `key` is looked up in app.i18n, `params` fill the text."""

    def __init__(self, key, field=None, **params):
        super().__init__(key)
        self.key = key
        self.field = field
        self.params = dict(params)
        if field:
            self.params.setdefault('field', field)


class ConfigError(AppError):
    """Invalid user settings."""


class GitError(AppError):
    """A git command failed."""


class Cancelled(Exception):
    """The user stopped the generation."""
