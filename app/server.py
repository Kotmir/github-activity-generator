"""Tiny local web server (stdlib only): serves index.html + assets and a
JSON API used by the UI. Bound to 127.0.0.1 and protected against
cross-site requests, because it can run git commands for the page."""
from __future__ import annotations

import json
import logging
import mimetypes
import os
import subprocess
import sys
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import __author__, __version__, ORIGINAL_AUTHOR, ORIGINAL_URL
from .config import (Config, MAX_COMMITS_LIMIT, MAX_DAYS_AFTER,
                     MAX_DAYS_BEFORE)
from .errors import AppError
from .generator import Generator
from .gitops import git_version, global_identity
from .i18n import normalize_lang, t
from .planner import build_schedule, summarize
from .reporter import LOG_FILE_NAME, Reporter

ROOT = Path(__file__).resolve().parent.parent
MAX_BODY = 64 * 1024
log = logging.getLogger('gag.server')


class JobManager:
    """Runs one generation at a time in a background thread."""

    def __init__(self, root):
        self.root = Path(root)
        self._lock = threading.Lock()
        self.reporter = None
        self.state = 'idle'   # idle | running | done | error | cancelled
        self.result = None

    def start(self, cfg, lang):
        with self._lock:
            if self.state == 'running':
                raise AppError('server.busy')
            self.reporter = Reporter(lang)
            self.state, self.result = 'running', None
        thread = threading.Thread(target=self._work, args=(cfg,),
                                  daemon=True)
        thread.start()

    def _work(self, cfg):
        generator = Generator(cfg, self.reporter, self.root)
        final = generator.execute()
        with self._lock:
            self.result = generator.result
            self.state = final

    def cancel(self):
        if self.reporter and self.state == 'running':
            self.reporter.cancel()

    def status(self, since, lang):
        rep = self.reporter
        if rep is None:
            return {'state': self.state, 'events': [], 'next': 0,
                    'progress': {'done': 0, 'total': 0}, 'result': None}
        events, nxt = rep.events_since(since, lang)
        return {'state': self.state, 'events': events, 'next': nxt,
                'progress': {'done': rep.done, 'total': rep.total},
                'result': self.result}


def open_folder(path):
    """Show a folder in the system file manager."""
    if sys.platform.startswith('win'):
        os.startfile(path)  # noqa: S606 - path comes from our own job
    elif sys.platform == 'darwin':
        subprocess.Popen(['open', path])
    else:
        subprocess.Popen(['xdg-open', path])


class Handler(BaseHTTPRequestHandler):
    server_version = 'ActivityGenerator/' + __version__
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *args):
        pass  # access log is too noisy (UI polls twice a second)

    def log_request(self, code='-', size='-'):
        try:
            failed = int(code) >= 400
        except (TypeError, ValueError):
            failed = False
        if failed:
            logging.getLogger('gag.http').warning(
                '%s "%s" -> %s', self.address_string(),
                self.requestline, code)

    # -- helpers ----------------------------------------------------
    @property
    def app(self):
        return self.server  # type: ignore[return-value]

    def _send(self, code, body, ctype, extra=None):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, payload):
        self._send(code, json.dumps(payload, ensure_ascii=False).encode(),
                   'application/json; charset=utf-8')

    def _fail(self, code, key, lang, **extra):
        payload = {'error': t(lang, key)}
        payload.update(extra)
        self._json(code, payload)

    def _host_ok(self):
        return self.headers.get('Host', '').lower() in self.app.allowed_hosts

    def _origin_ok(self):
        origin = self.headers.get('Origin')
        if not origin:
            return True
        return origin.lower() in {'http://' + h
                                  for h in self.app.allowed_hosts}

    def _body(self):
        try:
            size = int(self.headers.get('Content-Length') or 0)
        except ValueError:
            return None
        ctype = (self.headers.get('Content-Type') or '').lower()
        if size > MAX_BODY or not ctype.startswith('application/json'):
            return None
        try:
            data = json.loads(self.rfile.read(size) or b'{}')
        except ValueError:
            return None
        return data if isinstance(data, dict) else None

    # -- routing ----------------------------------------------------
    def do_GET(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)
        lang = normalize_lang((query.get('lang') or [''])[0])
        if not self._host_ok():
            return self._fail(403, 'server.forbidden', lang)
        path = url.path
        if path.startswith('/api/'):
            return self._api_get(path, query, lang)
        return self._static(path)

    def do_POST(self):
        url = urlparse(self.path)
        if not self._host_ok() or not self._origin_ok():
            return self._fail(403, 'server.forbidden', 'en')
        data = self._body()
        if data is None:
            return self._fail(400, 'server.bad_request', 'en')
        lang = normalize_lang(data.get('lang'))
        try:
            self._api_post(url.path, data, lang)
        except AppError as exc:
            code = 409 if exc.key == 'server.busy' else 400
            self._json(code, {'error': t(lang, exc.key, **exc.params),
                              'field': exc.field})

    # -- static files -----------------------------------------------
    def _static(self, path):
        if path in ('/', '/index.html'):
            target = ROOT / 'index.html'
        elif path.startswith('/assets/'):
            target = (ROOT / path.lstrip('/')).resolve()
            try:
                target.relative_to(ROOT / 'assets')
            except ValueError:
                return self._fail(404, 'server.not_found', 'en')
        else:
            return self._fail(404, 'server.not_found', 'en')
        if not target.is_file():
            return self._fail(404, 'server.not_found', 'en')
        ctype = mimetypes.guess_type(str(target))[0] or \
            'application/octet-stream'
        if ctype.startswith('text/') or ctype in (
                'application/javascript', 'image/svg+xml'):
            ctype += '; charset=utf-8'
        self._send(200, target.read_bytes(), ctype)

    # -- API --------------------------------------------------------
    def _api_get(self, path, query, lang):
        jobs = self.app.jobs
        if path == '/api/info':
            identity = global_identity() if git_version() else {}
            return self._json(200, {
                'version': __version__, 'author': __author__,
                'original_author': ORIGINAL_AUTHOR,
                'original_url': ORIGINAL_URL,
                'git': git_version(), 'identity': identity,
                'limits': {'max_commits': MAX_COMMITS_LIMIT,
                           'days_before': MAX_DAYS_BEFORE,
                           'days_after': MAX_DAYS_AFTER},
            })
        if path == '/api/status':
            try:
                since = max(0, int((query.get('since') or ['0'])[0]))
            except ValueError:
                since = 0
            return self._json(200, jobs.status(since, lang))
        if path == '/api/log/download':
            log_file = self.app.log_dir / LOG_FILE_NAME
            body = log_file.read_bytes()[-2_000_000:] \
                if log_file.exists() else b''
            return self._send(200, body, 'text/plain; charset=utf-8', {
                'Content-Disposition':
                    'attachment; filename="%s"' % LOG_FILE_NAME})
        return self._fail(404, 'server.not_found', lang)

    def _api_post(self, path, data, lang):
        jobs = self.app.jobs
        if path == '/api/preview':
            cfg = Config.from_dict(data)
            seed = cfg.seed if cfg.seed is not None else 0
            schedule = build_schedule(cfg, datetime.now(), seed)
            stats = summarize(schedule)
            stats.update({
                'start': schedule[0][0].strftime('%Y-%m-%d')
                if schedule else None,
                'counts': [c for _, c in schedule],
                'seed': seed,
            })
            return self._json(200, stats)
        if path == '/api/start':
            cfg = Config.from_dict(data)
            jobs.start(cfg, lang)
            return self._json(202, {'ok': True})
        if path == '/api/cancel':
            jobs.cancel()
            return self._json(200, {'ok': True})
        if path == '/api/open':
            result = jobs.result
            if not result or not Path(result['path']).is_dir():
                return self._fail(404, 'server.no_result', lang)
            open_folder(result['path'])
            return self._json(200, {'ok': True})
        if path == '/api/shutdown':
            self._json(200, {'ok': True})
            threading.Thread(target=self.app.shutdown, daemon=True).start()
            return None
        return self._fail(404, 'server.not_found', lang)


class AppServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, port, root=ROOT, log_dir=None):
        super().__init__(('127.0.0.1', port), Handler)
        self.port = self.server_address[1]
        self.allowed_hosts = {'127.0.0.1:%d' % self.port,
                              'localhost:%d' % self.port}
        self.jobs = JobManager(root)
        self.log_dir = Path(log_dir or Path(root) / 'logs')

    @property
    def url(self):
        return 'http://127.0.0.1:%d/' % self.port


def create_server(port=8765, root=ROOT, log_dir=None, tries=20):
    """Bind to `port`, or the next free one (port=0 → any free port)."""
    last_error = None
    for offset in range(tries if port else 1):
        try:
            return AppServer(port + offset if port else 0, root, log_dir)
        except OSError as exc:
            last_error = exc
    raise last_error
