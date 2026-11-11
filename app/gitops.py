"""Thin, safe wrapper around the git command line."""
from __future__ import annotations

import os
import shutil
import subprocess
import time

from .config import mask_secrets
from .errors import Cancelled, GitError

_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def git_version():
    """Return e.g. '2.43.0' or None when git is not installed."""
    if not shutil.which('git'):
        return None
    try:
        out = subprocess.run(
            ['git', '--version'], capture_output=True, text=True,
            timeout=15, creationflags=_NO_WINDOW).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return out.replace('git version', '').strip() or None


def global_identity():
    """Global git user.name / user.email (empty strings if unset)."""
    result = {}
    for key in ('name', 'email'):
        try:
            result[key] = subprocess.run(
                ['git', 'config', '--global', '--get', 'user.' + key],
                capture_output=True, text=True, encoding='utf-8',
                errors='replace', timeout=15,
                creationflags=_NO_WINDOW).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            result[key] = ''
    return result


class Git:
    """Runs git inside one repository directory.

    * never asks for input (no hanging on credential prompts);
    * disables commit signing / hooks for the bulk commits;
    * can be interrupted through `cancel_event`.
    """

    def __init__(self, cwd, cancel_event=None):
        self.cwd = str(cwd)
        self.cancel_event = cancel_event
        self.env = dict(os.environ)
        self.env.setdefault('GIT_TERMINAL_PROMPT', '0')
        self.env.setdefault('GIT_SSH_COMMAND', 'ssh -o BatchMode=yes')
        self.env['LC_ALL'] = 'C'

    def run(self, *args, env=None, check=True, timeout=None):
        cmd = ['git', '-c', 'commit.gpgsign=false'] + list(args)
        full_env = dict(self.env)
        if env:
            full_env.update(env)
        started = time.monotonic()
        proc = subprocess.Popen(
            cmd, cwd=self.cwd, env=full_env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            creationflags=_NO_WINDOW)
        while True:
            try:
                out, _ = proc.communicate(timeout=0.5)
                break
            except subprocess.TimeoutExpired:
                if self.cancel_event is not None and \
                        self.cancel_event.is_set():
                    proc.kill()
                    proc.communicate()
                    raise Cancelled()
                if timeout and time.monotonic() - started > timeout:
                    proc.kill()
                    proc.communicate()
                    raise GitError('git.timeout', cmd=args[0],
                                   seconds=int(timeout))
        text = (out or b'').decode('utf-8', errors='replace').strip()
        if check and proc.returncode != 0:
            raise GitError('git.cmd_failed', cmd=args[0],
                           code=proc.returncode,
                           output=mask_secrets(text)[-1500:])
        return text
