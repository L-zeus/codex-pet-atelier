"""Safety checks for the per-user helper installer; no GUI or account access."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import quota_bubble


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name).resolve()
        self.target = self.base / 'QuotaBubble'

    def tearDown(self):
        self.tmp.cleanup()

    def fake_compile(self, args, check=False, **kwargs):
        if args[0] == '/usr/bin/codesign':
            signature = Path(args[-1]) / 'Contents/_CodeSignature'
            signature.mkdir()
            (signature / 'CodeResources').write_bytes(b'synthetic seal')
        else:
            Path(args[args.index('-o') + 1]).write_bytes(b'synthetic executable')
        return mock.Mock(returncode=0)

    def install_fixture(self):
        def which(name):
            return {'swiftc': '/usr/bin/swiftc', 'codex': '/usr/bin/false'}.get(name)
        with mock.patch.object(quota_bubble.sys, 'platform', 'darwin'), \
             mock.patch.object(quota_bubble.shutil, 'which', side_effect=which), \
             mock.patch.object(quota_bubble.subprocess, 'run', side_effect=self.fake_compile):
            return quota_bubble.install(self.target)

    def test_install_verify_and_remove_owned_files(self):
        self.assertEqual(self.install_fixture()['status'], 'INSTALLED')
        self.assertTrue(quota_bubble.verify(self.target)['installed'])
        config = json.loads((self.target / 'config.json').read_text())
        config['codexCLI'] = '/missing/old/codex'
        (self.target / 'config.json').write_text(json.dumps(config))
        with self.assertRaisesRegex(ValueError, 'Codex CLI'):
            quota_bubble.verify(self.target)
        self.assertEqual(quota_bubble.uninstall(self.target)['status'], 'UNINSTALLED')
        self.assertFalse(self.target.exists())

    def test_unknown_or_modified_files_are_not_deleted(self):
        self.install_fixture()
        extra = self.target / 'personal.txt'
        extra.write_text('keep')
        with self.assertRaisesRegex(ValueError, '未知'):
            quota_bubble.uninstall(self.target)
        self.assertEqual(extra.read_text(), 'keep')
        extra.unlink()
        (self.target / 'show-quota-bubble').write_text('changed')
        with self.assertRaisesRegex(ValueError, '变化'):
            quota_bubble.uninstall(self.target)
        self.assertTrue(self.target.exists())

    def test_unowned_existing_directory_is_not_replaced(self):
        self.target.mkdir()
        (self.target / 'keep').write_text('keep')
        with self.assertRaises((ValueError, OSError)):
            self.install_fixture()
        self.assertEqual((self.target / 'keep').read_text(), 'keep')

    def test_upgrade_previous_owned_installation(self):
        self.install_fixture()
        signature = self.target / 'QuotaBubble.app/Contents/_CodeSignature'
        (signature / 'CodeResources').unlink()
        signature.rmdir()
        metadata_path = self.target / 'installed.json'
        metadata = json.loads(metadata_path.read_text())
        metadata['files'].pop('QuotaBubble.app/Contents/_CodeSignature/CodeResources')
        metadata_path.write_text(json.dumps(metadata))
        self.assertEqual(self.install_fixture()['status'], 'INSTALLED')
        self.assertTrue(quota_bubble.verify(self.target)['installed'])


@unittest.skipIf(os.name == 'nt', 'signal behavior is specific to POSIX')
class ProcessCleanupTests(unittest.TestCase):
    def test_interrupting_query_stops_its_app_server(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory).resolve()
            pid_file = directory / 'pid'
            fake = directory / 'fake-codex'
            fake.write_text('#!/usr/bin/env python3\nimport os,time\n'
                            f'open({str(pid_file)!r}, "w").write(str(os.getpid()))\n'
                            'time.sleep(30)\n')
            fake.chmod(0o700)
            reader = Path(__file__).resolve().parents[1] / 'scripts/codex_usage.py'
            process = subprocess.Popen([sys.executable, str(reader), '--json', '--codex-cli', str(fake)],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                deadline = time.monotonic() + 8
                while not pid_file.exists() and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertTrue(pid_file.exists(), 'synthetic app server did not start')
                child = int(pid_file.read_text())
                process.send_signal(signal.SIGINT)
                process.wait(timeout=8)
                with self.assertRaises(ProcessLookupError):
                    os.kill(child, 0)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()


if __name__ == '__main__':
    unittest.main()
