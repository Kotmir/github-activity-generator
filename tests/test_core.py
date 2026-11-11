import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from subprocess import check_output

from app.config import Config, mask_secrets
from app.errors import ConfigError
from app.generator import Generator, repo_dirname
from app.i18n import MESSAGES, t
from app.planner import build_schedule, summarize
from app.reporter import Reporter, reset_logging, setup_logging

HAS_GIT = shutil.which('git') is not None
NOW = datetime(2026, 11, 11, 12, 0)


class ConfigTests(unittest.TestCase):
    def test_defaults(self):
        cfg = Config.from_dict({})
        self.assertEqual((cfg.days_before, cfg.frequency, cfg.max_commits),
                         (365, 80, 10))
        self.assertIsNone(cfg.repository)

    def test_string_numbers_from_form(self):
        cfg = Config.from_dict({'days_before': '30', 'frequency': '55',
                                'seed': '42'})
        self.assertEqual((cfg.days_before, cfg.frequency, cfg.seed),
                         (30, 55, 42))

    def test_rejects_bad_values(self):
        for data in ({'frequency': 101}, {'max_commits': 0},
                     {'max_commits': 21}, {'days_before': -1},
                     {'days_before': 'abc'}, {'days_before': True},
                     {'mode': 'x'}, {'user_email': 'nope'},
                     {'repository': '--upload-pack=evil'},
                     {'repository': 'not a url'},
                     {'user_name': '-bad'},
                     {'days_before': 3650, 'days_after': 365}):
            with self.assertRaises(ConfigError, msg=str(data)):
                Config.from_dict(data)

    def test_accepts_remote_formats(self):
        for url in ('https://github.com/u/r.git', 'git@github.com:u/r.git',
                    'ssh://git@github.com/u/r.git'):
            self.assertEqual(Config.from_dict({'repository': url})
                             .repository, url)

    def test_mask_secrets(self):
        self.assertEqual(
            mask_secrets('https://me:tok3n@github.com/u/r.git'),
            'https://***@github.com/u/r.git')

    def test_repo_dirname(self):
        for url in ('https://github.com/u/my-repo.git',
                    'https://github.com/u/my-repo',
                    'git@github.com:u/my-repo.git'):
            self.assertEqual(repo_dirname(url, NOW), 'my-repo')
        self.assertTrue(repo_dirname(None, NOW).startswith('repository-'))


class I18nTests(unittest.TestCase):
    def test_languages_have_same_keys(self):
        self.assertEqual(set(MESSAGES['ru']), set(MESSAGES['en']))

    def test_translate(self):
        self.assertIn('Git', t('en', 'git.version', version='2'))
        self.assertIn('найден', t('ru', 'git.version', version='2'))
        self.assertEqual(t('ru', 'unknown.key'), 'unknown.key')


class PlannerTests(unittest.TestCase):
    def cfg(self, **kw):
        return Config.from_dict(dict({'seed': 7}, **kw))

    def test_same_seed_same_plan(self):
        a = build_schedule(self.cfg(), NOW)
        b = build_schedule(self.cfg(), NOW)
        self.assertEqual(a, b)
        self.assertNotEqual(a, build_schedule(self.cfg(seed=8), NOW))

    def test_length_and_bounds(self):
        cfg = self.cfg(days_before=30, days_after=5, max_commits=3)
        plan = build_schedule(cfg, NOW)
        self.assertEqual(len(plan), 35)
        self.assertTrue(all(0 <= c <= 3 for _, c in plan))

    def test_frequency_extremes(self):
        zero = summarize(build_schedule(self.cfg(frequency=0), NOW))
        full = summarize(build_schedule(self.cfg(frequency=100), NOW))
        self.assertEqual(zero['total'], 0)
        self.assertEqual(full['active_days'], 365)

    def test_no_weekends(self):
        plan = build_schedule(self.cfg(no_weekends=True, frequency=100),
                              NOW)
        self.assertTrue(all(c == 0 for d, c in plan if d.weekday() >= 5))
        self.assertTrue(any(c > 0 for _, c in plan))


@unittest.skipUnless(HAS_GIT, 'git is not installed')
class GeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        reset_logging()
        setup_logging(cls.tmp / 'logs', console=False)

    @classmethod
    def tearDownClass(cls):
        reset_logging()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_job(self, **kw):
        data = {'user_name': 'tester', 'user_email': 't@example.com',
                'days_before': 6, 'days_after': 2, 'frequency': 100,
                'max_commits': 3, 'seed': 5, 'output_dir': str(self.tmp)}
        data.update(kw)
        cfg = Config.from_dict(data)
        rep = Reporter('en')
        gen = Generator(cfg, rep, self.tmp)
        return gen, rep, gen.execute(), cfg

    def count(self, path):
        return int(check_output(['git', '-C', path, 'rev-list', '--count',
                                 'HEAD']).decode())

    def test_file_mode(self):
        gen, rep, state, cfg = self.run_job()
        self.assertEqual(state, 'done')
        expected = summarize(build_schedule(cfg, datetime.now()))['total']
        self.assertEqual(gen.result['commits'], expected)
        self.assertEqual(self.count(gen.result['path']), expected)
        branch = check_output(['git', '-C', gen.result['path'], 'branch',
                               '--show-current']).decode().strip()
        self.assertEqual(branch, 'main')
        self.assertEqual((rep.done, rep.total), (expected, expected))
        self.assertTrue((Path(gen.result['path']) / 'README.md').exists())

    def test_empty_mode_and_dates(self):
        gen, _, state, _ = self.run_job(mode='empty', days_before=3,
                                        days_after=0)
        self.assertEqual(state, 'done')
        dates = check_output(['git', '-C', gen.result['path'], 'log',
                              '--format=%ad|%cd|%s',
                              '--date=format:%Y-%m-%d %H']).decode()
        for line in dates.strip().splitlines():
            author, committer, subject = line.split('|')
            self.assertEqual(author, committer)
            self.assertTrue(author.endswith(' 20'))
            self.assertTrue(subject.startswith('Contribution: '))
            self.assertNotIn('"', subject)

    def test_cancel(self):
        cfg = Config.from_dict({
            'user_name': 'tester', 'user_email': 't@example.com',
            'days_before': 20, 'frequency': 100, 'seed': 1,
            'output_dir': str(self.tmp)})
        rep = Reporter('ru')
        rep.cancel()
        self.assertEqual(Generator(cfg, rep, self.tmp).execute(),
                         'cancelled')

    def test_empty_plan_is_an_error(self):
        _, rep, state, _ = self.run_job(frequency=0)
        self.assertEqual(state, 'error')
        events, _ = rep.events_since(0)
        self.assertEqual(events[-1]['level'], 'error')

    def test_events_follow_language(self):
        _, rep, _, _ = self.run_job(days_before=2)
        en, _ = rep.events_since(0, 'en')
        ru, _ = rep.events_since(0, 'ru')
        self.assertEqual(len(en), len(ru))
        self.assertNotEqual(en[0]['text'], ru[0]['text'])


if __name__ == '__main__':
    unittest.main()
