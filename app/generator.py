"""The generator itself: creates a repository full of dated commits."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path

from .config import mask_secrets
from .errors import AppError, Cancelled, ConfigError, GitError
from .gitops import Git, git_version
from .planner import build_schedule, commit_message, summarize

PUSH_TIMEOUT = 900


def repo_dirname(repository, now):
    """Folder name from the remote URL, or a timestamped fallback."""
    if repository:
        name = repository.rstrip('/').rsplit('/', 1)[-1]
        name = name.rsplit(':', 1)[-1]
        if name.endswith('.git'):
            name = name[:-4]
        name = re.sub(r'[^\w.\-]', '_', name).strip('.')
        if name:
            return name
    return 'repository-' + now.strftime('%Y-%m-%d-%H-%M-%S')


def unique_dir(parent, name):
    candidate, n = parent / name, 2
    while candidate.exists():
        candidate = parent / ('%s-%d' % (name, n))
        n += 1
    return candidate


class Generator:
    def __init__(self, cfg, reporter, base_dir=None):
        self.cfg = cfg
        self.rep = reporter
        self.base_dir = Path(base_dir or Path.cwd())
        self.result = None   # {'path': ..., 'commits': ...} after success

    # -- public -----------------------------------------------------
    def execute(self):
        """Run and never raise. Returns done | cancelled | error."""
        try:
            self._run()
            return 'done'
        except Cancelled:
            self.rep.log('warning', 'job.cancelled')
            return 'cancelled'
        except AppError as exc:
            self.rep.log('error', exc.key, **exc.params)
            if exc.key == 'git.cmd_failed' and exc.params.get('cmd') \
                    == 'push':
                self.rep.log('warning', 'push.fail')
            return 'error'
        except Exception as exc:  # noqa: BLE001 - last line of defence
            import logging
            logging.getLogger('gag').exception('unexpected error')
            self.rep.log('error', 'job.error', error=str(exc))
            return 'error'

    # -- steps ------------------------------------------------------
    def _run(self):
        cfg, rep = self.cfg, self.rep
        rep.log('info', 'job.start')

        version = git_version()
        if not version:
            raise GitError('git.missing')
        rep.log('info', 'git.version', version=version)

        now = datetime.now()
        seed = cfg.seed if cfg.seed is not None else \
            int(now.timestamp() * 1000) % 10 ** 9
        schedule = build_schedule(cfg, now, seed)
        stats = summarize(schedule)
        active = [(d, c) for d, c in schedule if c > 0]
        if not active:
            raise ConfigError('plan.empty')
        rep.log('info', 'plan.summary', commits=stats['total'],
                days=stats['active_days'],
                first=active[0][0].strftime('%Y-%m-%d'),
                last=active[-1][0].strftime('%Y-%m-%d'),
                mode=cfg.mode, seed=seed)
        rep.progress(0, stats['total'])

        repo_dir = self._prepare_dir(now)
        git = Git(repo_dir, rep.cancel_event)
        self._init_repo(git)
        self._set_identity(git)
        self._commit_all(git, repo_dir, active, stats['total'])
        pushed = self._push(git)

        self.result = {'path': str(repo_dir), 'commits': stats['total'],
                       'pushed': pushed}
        rep.log('success', 'job.finished', path=str(repo_dir))
        if pushed:
            rep.log('info', 'job.reindex')

    def _prepare_dir(self, now):
        out_root = Path(self.cfg.output_dir).expanduser()
        if not out_root.is_absolute():
            out_root = self.base_dir / out_root
        out_root.mkdir(parents=True, exist_ok=True)
        repo_dir = unique_dir(out_root,
                              repo_dirname(self.cfg.repository, now))
        repo_dir.mkdir()
        self.rep.log('info', 'repo.dir', path=str(repo_dir))
        return repo_dir

    def _init_repo(self, git):
        git.run('init', '-q')
        # `git init -b` needs git >= 2.28, this works everywhere.
        git.run('symbolic-ref', 'HEAD', 'refs/heads/main')
        self.rep.log('info', 'repo.init')

    def _set_identity(self, git):
        cfg = self.cfg
        if cfg.user_name:
            git.run('config', 'user.name', cfg.user_name)
        if cfg.user_email:
            git.run('config', 'user.email', cfg.user_email)
        name = git.run('config', '--get', 'user.name', check=False)
        email = git.run('config', '--get', 'user.email', check=False)
        if not name or not email:
            raise GitError('identity.missing')
        key = 'identity.set' if (cfg.user_name or cfg.user_email) \
            else 'identity.global'
        self.rep.log('info', key, name=name, email=email)

    def _commit_all(self, git, repo_dir, active, total):
        rep, cfg = self.rep, self.cfg
        readme = repo_dir / 'README.md'
        done, last_pct, first = 0, 0, True
        for day, count in active:
            rep.log('debug', 'day.commits',
                    date=day.strftime('%Y-%m-%d'), n=count)
            for minute in range(count):
                rep.check_cancelled()
                moment = day + timedelta(minutes=minute)
                msg = commit_message(moment)
                stamp = moment.strftime('%Y-%m-%dT%H:%M:%S')
                env = {'GIT_AUTHOR_DATE': stamp,
                       'GIT_COMMITTER_DATE': stamp}
                if cfg.mode == 'file':
                    with open(readme, 'a', encoding='utf-8',
                              newline='\n') as handle:
                        handle.write(msg + '\n\n')
                    if first:
                        git.run('add', 'README.md')
                    args = ['commit', '-q', '--no-verify']
                    if not first:
                        args.append('-a')
                else:
                    args = ['commit', '-q', '--no-verify', '--allow-empty']
                git.run(*(args + ['-m', msg]), env=env)
                first = False
                done += 1
                rep.progress(done, total)
                pct = done * 100 // total
                if pct // 10 != last_pct // 10 and pct < 100:
                    rep.log('info', 'commits.progress', done=done,
                            total=total, pct=pct)
                last_pct = pct
        rep.log('info', 'commits.done', total=total)

    def _push(self, git):
        repo = self.cfg.repository
        if not repo:
            self.rep.log('info', 'push.skipped')
            return False
        self.rep.log('info', 'push.remote', url=mask_secrets(repo))
        git.run('remote', 'add', 'origin', repo)
        git.run('branch', '-M', 'main')
        self.rep.log('info', 'push.start')
        git.run('push', '-u', 'origin', 'main', timeout=PUSH_TIMEOUT)
        self.rep.log('success', 'push.ok')
        return True
