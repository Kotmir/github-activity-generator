import json
import shutil
import tempfile
import threading
import time
import unittest
from http.client import HTTPConnection
from pathlib import Path

from app.reporter import reset_logging, setup_logging
from app.server import ROOT, create_server

HAS_GIT = shutil.which('git') is not None


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        reset_logging()
        setup_logging(cls.tmp / 'logs', console=False)
        cls.server = create_server(0, ROOT, cls.tmp / 'logs')
        cls.thread = threading.Thread(target=cls.server.serve_forever,
                                      daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        reset_logging()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def call(self, method, path, body=None, headers=None):
        conn = HTTPConnection('127.0.0.1', self.server.port, timeout=10)
        hdrs = dict(headers or {})
        data = None
        if body is not None:
            data = json.dumps(body)
            hdrs.setdefault('Content-Type', 'application/json')
        conn.request(method, path, data, hdrs)
        res = conn.getresponse()
        raw = res.read()
        conn.close()
        return res.status, raw, res

    def test_index_and_assets(self):
        status, raw, res = self.call('GET', '/')
        self.assertEqual(status, 200)
        self.assertIn(b'kotmir', raw)
        self.assertIn('text/html', res.getheader('Content-Type'))
        for path in ('/assets/css/style.css', '/assets/js/app.js',
                     '/assets/js/i18n.js', '/assets/img/logo.svg'):
            self.assertEqual(self.call('GET', path)[0], 200, path)

    def test_no_path_traversal(self):
        for path in ('/assets/../run.py', '/assets/%2e%2e/run.py',
                     '/app/server.py', '/run.py'):
            self.assertEqual(self.call('GET', path)[0], 404, path)

    def test_rejects_foreign_host_and_origin(self):
        self.assertEqual(
            self.call('GET', '/api/info', headers={'Host': 'evil.com'})[0],
            403)
        status, _, _ = self.call('POST', '/api/cancel', {},
                                 {'Origin': 'http://evil.com'})
        self.assertEqual(status, 403)
        status, _, _ = self.call('POST', '/api/cancel', {},
                                 {'Content-Type': 'text/plain'})
        self.assertEqual(status, 400)

    def test_info_and_preview(self):
        status, raw, _ = self.call('GET', '/api/info')
        self.assertEqual(status, 200)
        info = json.loads(raw)
        self.assertEqual(info['author'], 'kotmir')
        status, raw, _ = self.call('POST', '/api/preview', {
            'days_before': 40, 'frequency': 100, 'seed': 3})
        data = json.loads(raw)
        self.assertEqual(len(data['counts']), 40)
        self.assertEqual(data['total'], sum(data['counts']))

    def test_validation_errors_are_localised(self):
        _, raw, _ = self.call('POST', '/api/preview',
                              {'frequency': 500, 'lang': 'ru'})
        err = json.loads(raw)
        self.assertEqual(err['field'], 'frequency')
        self.assertIn('должно быть', err['error'])
        _, raw, _ = self.call('POST', '/api/preview',
                              {'frequency': 500, 'lang': 'en'})
        self.assertIn('must be between', json.loads(raw)['error'])

    @unittest.skipUnless(HAS_GIT, 'git is not installed')
    def test_full_job(self):
        body = {'user_name': 'tester', 'user_email': 't@example.com',
                'days_before': 4, 'frequency': 100, 'max_commits': 2,
                'seed': 9, 'mode': 'empty', 'lang': 'en',
                'output_dir': str(self.tmp / 'out')}
        status, _, _ = self.call('POST', '/api/start', body)
        self.assertEqual(status, 202)
        deadline = time.time() + 30
        since, texts, state = 0, [], 'running'
        while state == 'running' and time.time() < deadline:
            _, raw, _ = self.call('GET', '/api/status?since=%d&lang=en'
                                  % since)
            data = json.loads(raw)
            texts += [e['text'] for e in data['events']]
            since, state = data['next'], data['state']
            time.sleep(0.1)
        self.assertEqual(state, 'done', texts)
        self.assertTrue(any('Done!' in x for x in texts))
        self.assertTrue(Path(data['result']['path']).is_dir())
        status, raw, _ = self.call('GET', '/api/log/download')
        self.assertEqual(status, 200)
        self.assertIn(b'Generation started', raw)


if __name__ == '__main__':
    unittest.main()
