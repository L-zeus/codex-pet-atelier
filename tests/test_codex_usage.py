"""Offline tests for the app-server reader; never access a personal account."""
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import codex_usage


class NormalizationTests(unittest.TestCase):
    def test_multi_bucket_and_legacy_precedence(self):
        value = codex_usage.normalize({
            'rateLimits': {'limitId': 'old', 'primary': {'usedPercent': 99}},
            'rateLimitsByLimitId': {
                'codex': {'limitName': 'Codex', 'primary': {'usedPercent': 25, 'windowDurationMins': 300, 'resetsAt': 2000000000},
                          'secondary': {'usedPercent': 110, 'windowDurationMins': 10080, 'resetsAt': 2000001000},
                          'credits': {'hasCredits': True, 'balance': '3.5'}},
                'other': {'primary': {'usedPercent': 0, 'windowDurationMins': 60, 'resetsAt': None}},
            }, 'rateLimitResetCredits': {'availableCount': 2, 'credits': [{'id': 'do-not-copy'}]},
        })
        self.assertEqual(value['status'], 'ok')
        self.assertEqual([b['id'] for b in value['buckets']], ['codex', 'other'])
        self.assertEqual([w['remainingPercent'] for w in value['buckets'][0]['windows']], [75, 0])
        self.assertEqual(value['buckets'][0]['windows'][1]['durationMins'], 10080)
        self.assertEqual(value['resetCreditsAvailable'], 2)
        self.assertNotIn('do-not-copy', json.dumps(value))

    def test_single_week_missing_and_bad_values(self):
        value = codex_usage.normalize({'rateLimits': {'secondary': {'usedPercent': 48.5,
            'windowDurationMins': 10080, 'resetsAt': 2000000000}}})
        self.assertEqual(len(value['buckets'][0]['windows']), 1)
        self.assertEqual(value['buckets'][0]['windows'][0]['remainingPercent'], 51.5)
        self.assertEqual(codex_usage.normalize({'rateLimits': None})['status'], 'unavailable')
        bad = codex_usage.normalize({'rateLimits': {'primary': {'usedPercent': -1,
            'windowDurationMins': 0, 'resetsAt': -1}}})['buckets'][0]['windows'][0]
        self.assertIsNone(bad['usedPercent'])
        self.assertIsNone(bad['durationMins'])
        self.assertIsNone(bad['resetsAt'])
        self.assertEqual(codex_usage.display_time(None), '未提供')

    def test_snapshot_rejects_traversal_and_nonlocal_path(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = str(Path(directory).resolve())
            with mock.patch.object(codex_usage, 'ROOT', Path(directory)):
                with self.assertRaises(ValueError):
                    codex_usage.write_snapshot(Path(directory) / 'workruns/../../outside.json', {})
                preserved = Path(directory) / 'workruns/keep.json'
                preserved.parent.mkdir()
                preserved.write_text('{"existing": true}')
                with self.assertRaises(ValueError):
                    codex_usage.write_snapshot(preserved, {})
                self.assertEqual(json.loads(preserved.read_text()), {'existing': True})
                package = preserved.parent / 'pet-package'
                package.mkdir()
                (package / 'pet.json').write_text('{}')
                with self.assertRaises(ValueError):
                    codex_usage.write_snapshot(package / 'snapshot.json', {})
                target = Path(directory) / 'workruns/usage.json'
                codex_usage.write_snapshot(target, {'status': 'unavailable', 'source': codex_usage.SOURCE})
                self.assertEqual(json.loads(target.read_text())['status'], 'unavailable')
                codex_usage.write_snapshot(target, {'status': 'error', 'source': codex_usage.SOURCE})
                if os.name != 'nt':
                    self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)

    def test_missing_cli(self):
        with mock.patch.object(codex_usage.shutil, 'which', return_value=None):
            with self.assertRaises(codex_usage.UsageError) as cm:
                codex_usage.fetch_usage()
        self.assertEqual(cm.exception.status, 'cli_missing')


@unittest.skipIf(os.name == 'nt', 'executable fixture uses a POSIX shebang')
class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.executable = Path(self.temp.name) / 'fake-codex'
        self.executable.write_text('''#!/usr/bin/env python3
import json, os, sys, time
mode = os.environ.get('ATELIER_FAKE_MODE', 'ok')
def recv(): return json.loads(sys.stdin.readline())
def send(obj): print(json.dumps(obj), flush=True)
request = recv()
if mode == 'timeout': time.sleep(3); sys.exit(0)
if mode == 'bad': print('not-json', flush=True); sys.exit(0)
if mode == 'permission': print('Error: Operation not permitted', file=sys.stderr, flush=True); sys.exit(1)
send({'method':'notice','params':{}})
send({'id':request['id'],'result':{}})
notification = recv()
assert notification['method'] == 'initialized'
request = recv()
assert request['method'] == 'account/read' and request['params']['refreshToken'] is False
account = None if mode == 'no_auth' else {'type':'chatgpt','email':'never-return-this'}
send({'id':request['id'],'result':{'account':account}})
if account is not None:
    request = recv()
    assert request['method'] == 'account/rateLimits/read'
    if mode == 'error': send({'id':request['id'],'error':{'code':-32601,'message':'private-detail'}})
    else: send({'id':request['id'],'result':{'rateLimits':{'primary':{'usedPercent':25,'windowDurationMins':300,'resetsAt':2000000000}}}})
''', encoding='utf-8')
        self.executable.chmod(0o700)

    def tearDown(self):
        self.temp.cleanup()

    def test_real_subprocess_handshake_and_filtered_response(self):
        with mock.patch.dict(os.environ, {'ATELIER_FAKE_MODE': 'ok'}):
            result = codex_usage.fetch_usage(timeout=2, executable=str(self.executable))
        self.assertEqual(result['buckets'][0]['windows'][0]['remainingPercent'], 75)
        self.assertNotIn('never-return-this', json.dumps(result))

    def test_auth_protocol_and_timeout(self):
        for mode, expected in [('no_auth', 'auth_required'), ('bad', 'protocol_error'), ('permission', 'error'),
                               ('error', 'protocol_error'), ('timeout', 'timeout')]:
            with self.subTest(mode=mode), mock.patch.dict(os.environ, {'ATELIER_FAKE_MODE': mode}):
                with self.assertRaises(codex_usage.UsageError) as cm:
                    codex_usage.fetch_usage(timeout=0.2 if mode == 'timeout' else 3,
                                            executable=str(self.executable))
                self.assertEqual(cm.exception.status, expected)
                self.assertNotIn('private-detail', str(cm.exception))


class HtmlPageTests(unittest.TestCase):
    def test_json_accepts_explicit_cli_without_opening_browser(self):
        result = codex_usage.normalize({'rateLimits': {'primary': {'usedPercent': 50}}})
        with mock.patch.object(codex_usage, 'fetch_usage', return_value=result) as fetch, \
             mock.patch.object(codex_usage.webbrowser, 'open') as browser, mock.patch('builtins.print'):
            self.assertEqual(codex_usage.main(['--json', '--codex-cli', '/example/codex']), 0)
            fetch.assert_called_once_with(15, executable='/example/codex')
            browser.assert_not_called()

    def test_permission_multi_bucket_html_escape_and_stale(self):
        value = codex_usage.normalize({
            'ordinaryUsageAllowed': False,
            'rateLimitsByLimitId': {
                'codex': {'limitName': '<script>alert(1)</script>', 'rateLimitReachedType': 'rateLimitReached',
                          'primary': {'usedPercent': 25, 'windowDurationMins': 300, 'resetsAt': 2000000000},
                          'secondary': {'usedPercent': 60, 'windowDurationMins': 10080, 'resetsAt': 2000000000}},
                'other': {'primary': {'usedPercent': 5, 'windowDurationMins': 45, 'resetsAt': None}}}})
        page = codex_usage.render_html(value)
        self.assertIn('不允许正常使用', page)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', page)
        self.assertNotIn('<script>', page)
        self.assertIn('剩余 75%', page)
        self.assertIn('已使用 25%', page)
        self.assertIn('5 小时', page)
        self.assertIn('每周', page)
        self.assertIn('45 分钟', page)
        self.assertIn('Content-Security-Policy', page)
        self.assertNotIn('<button', page)
        value['ordinaryUsageAllowed'] = None
        value['fetchedAt'] = '2020-01-01T00:00:00+00:00'
        page = codex_usage.render_html(value)
        self.assertIn('正常使用许可状态未提供', page)
        self.assertIn('已过期', page)

    def test_open_queries_once_and_writes_private_page(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(codex_usage, 'ROOT', Path(directory).resolve()):
            result = codex_usage.normalize({'rateLimits': {'primary': {'usedPercent': 50, 'windowDurationMins': 300}}})
            with mock.patch.object(codex_usage, 'fetch_usage', return_value=result) as fetch, \
                 mock.patch.object(codex_usage.webbrowser, 'open', return_value=True) as browser, \
                 mock.patch('builtins.print'):
                self.assertEqual(codex_usage.main(['--open']), 0)
                fetch.assert_called_once()
                browser.assert_called_once()
            pages = list((Path(directory) / 'workruns/codex-usage-pages').glob('*.html'))
            self.assertEqual(len(pages), 1)
            self.assertIn('剩余 50%', pages[0].read_text())
            if os.name != 'nt':
                self.assertEqual(stat.S_IMODE(pages[0].stat().st_mode), 0o600)
                self.assertEqual(stat.S_IMODE(pages[0].parent.stat().st_mode), 0o700)

    def test_open_error_is_new_page_not_stale_success(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(codex_usage, 'ROOT', Path(directory).resolve()), \
             mock.patch.object(codex_usage, 'fetch_usage', side_effect=codex_usage.UsageError('auth_required', '未登录')), \
             mock.patch.object(codex_usage.webbrowser, 'open', return_value=True), mock.patch('builtins.print'):
            self.assertEqual(codex_usage.main(['--open']), 1)
            page = next((Path(directory) / 'workruns/codex-usage-pages').glob('*.html')).read_text()
            self.assertIn('未登录', page)
            self.assertNotIn('剩余 50%', page)


if __name__ == '__main__':
    unittest.main()
