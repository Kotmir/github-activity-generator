#!/usr/bin/env python
"""Launcher: starts the local server and opens the web UI in the browser.

    python run.py [--port 8765] [--no-browser] [--lang ru|en]

Author: kotmir
"""
import argparse
import logging
import os
import sys
import threading
import webbrowser

from app import __author__, __version__
from app.i18n import t
from app.reporter import setup_logging
from app.server import ROOT, create_server

BANNER = r"""
  ┌──────────────────────────────────────────────┐
  │   GitHub Activity Generator  v{ver:<15}│
  │   author: {author:<35}│
  └──────────────────────────────────────────────┘
"""


def disable_quick_edit():
    """Windows: a click inside the console enters 'Select' mode and
    freezes the process. Turn that mode off so the server never stalls."""
    if os.name != 'nt':
        return
    try:
        import ctypes
        kernel = ctypes.windll.kernel32
        handle = kernel.GetStdHandle(-10)          # STD_INPUT_HANDLE
        mode = ctypes.c_uint32()
        if kernel.GetConsoleMode(handle, ctypes.byref(mode)):
            new_mode = (mode.value & ~0x0040) | 0x0080   # QUICK_EDIT off
            kernel.SetConsoleMode(handle, new_mode)
    except Exception:  # noqa: BLE001 - purely cosmetic safety net
        pass


def main():
    disable_quick_edit()
    parser = argparse.ArgumentParser(description='GitHub Activity Generator')
    parser.add_argument('--port', type=int, default=8765,
                        help='port (default 8765, 0 = any free)')
    parser.add_argument('--no-browser', action='store_true',
                        help='do not open the browser / не открывать браузер')
    parser.add_argument('--lang', choices=['ru', 'en'], default='ru',
                        help='console language / язык консоли')
    args = parser.parse_args()

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')

    setup_logging(ROOT / 'logs')
    try:
        server = create_server(args.port, ROOT)
    except OSError as exc:
        print('Cannot start the server / Не удалось запустить сервер: %s'
              % exc, file=sys.stderr)
        return 1

    print(BANNER.format(ver=__version__, author=__author__))
    logging.getLogger('gag').info(t(args.lang, 'server.started',
                                    url=server.url))
    print('  Ctrl+C — stop / остановить\n')
    if not args.no_browser:
        threading.Timer(0.6, webbrowser.open, args=(server.url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        logging.getLogger('gag').info(t(args.lang, 'server.stopped'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
