"""Command line interface (kept compatible with the original script)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import Config, MAX_COMMITS_LIMIT
from .errors import AppError
from .generator import Generator
from .i18n import t
from .reporter import Reporter, setup_logging


def build_parser():
    p = argparse.ArgumentParser(
        description='GitHub Activity Generator · author: kotmir. '
                    'Run "python run.py" for the web interface.')
    p.add_argument('-nw', '--no_weekends', action='store_true',
                   help='do not commit on weekends / без выходных')
    p.add_argument('-mc', '--max_commits', type=int, default=10,
                   help='max commits per day, 1-%d (default 10) / '
                        'максимум коммитов в день' % MAX_COMMITS_LIMIT)
    p.add_argument('-fr', '--frequency', type=int, default=80,
                   help='percent of days with commits (default 80) / '
                        'процент дней с коммитами')
    p.add_argument('-r', '--repository', type=str,
                   help='empty remote repository URL; if set, changes '
                        'are pushed / адрес пустого репозитория')
    p.add_argument('-un', '--user_name', type=str,
                   help='override git user.name / имя автора')
    p.add_argument('-ue', '--user_email', type=str,
                   help='override git user.email / e-mail автора')
    p.add_argument('-db', '--days_before', type=int, default=365,
                   help='days before today to start (default 365) / '
                        'дней назад')
    p.add_argument('-da', '--days_after', type=int, default=0,
                   help='days after today to continue / дней вперёд')
    p.add_argument('--mode', choices=['file', 'empty'], default='file',
                   help='file: edit README.md, empty: empty commits')
    p.add_argument('--seed', type=int, help='random seed (repeatable graph)')
    p.add_argument('--out', default='output', help='output folder')
    p.add_argument('--lang', choices=['ru', 'en'], default='ru',
                   help='log language / язык логов')
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    lang = args.lang
    base = Path.cwd()
    setup_logging(base / 'logs')
    try:
        cfg = Config.from_dict({
            'repository': args.repository, 'user_name': args.user_name,
            'user_email': args.user_email, 'days_before': args.days_before,
            'days_after': args.days_after, 'frequency': args.frequency,
            'max_commits': args.max_commits, 'no_weekends': args.no_weekends,
            'mode': args.mode, 'seed': args.seed, 'output_dir': args.out})
    except AppError as exc:
        print(t(lang, exc.key, **exc.params), file=sys.stderr)
        return 2
    generator = Generator(cfg, Reporter(lang), base)
    try:
        state = generator.execute()
    except KeyboardInterrupt:
        state = 'cancelled'
    return 0 if state == 'done' else 1
