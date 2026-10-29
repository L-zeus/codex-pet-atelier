"""Shortcut ownership, rollback, and Windows Shell round-trip without account data."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import windows_quota

spec = importlib.util.spec_from_file_location('windows_bubble', ROOT / 'windows/quota_bubble.py')
windows_bubble = importlib.util.module_from_spec(spec)
spec.loader.exec_module(windows_bubble)


class HotkeyTests(unittest.TestCase):
    def test_valid_and_invalid_combinations(self):
        self.assertEqual(windows_quota.normalize_hotkey('alt+ctrl+q'), 'CTRL+ALT+Q')
        self.assertEqual(windows_quota.normalize_hotkey('shift+ctrl+F12'), 'CTRL+SHIFT+F12')
        for key in ('Q', 'CTRL+Q', 'CTRL+CTRL+Q', 'CTRL+ALT+F13', 'WIN+ALT+Q'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                windows_quota.normalize_hotkey(key)

    def test_reader_cleanup_falls_back_when_taskkill_fails(self):
        process = mock.Mock(pid=123)
        process.poll.return_value = None
        with mock.patch.object(windows_bubble.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)):
            windows_bubble.terminate_tree(process)
        process.terminate.assert_called_once()

    def test_display_helpers_for_reported_windows(self):
        self.assertEqual(windows_bubble.duration(300), '5 小时')
        self.assertEqual(windows_bubble.duration(10080), '每周')
        self.assertEqual(windows_bubble.duration(None), '窗口时长未提供')
        self.assertEqual(windows_bubble.local_time(None), '未提供')


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name).resolve()
        self.folder = self.base / 'start' / 'Codex Pet Atelier'
        self.config = self.base / 'workruns' / 'config.json'
        self.ui = self.base / 'quota_bubble.py'
        self.ui.touch()
        self.python = self.base / 'python.exe'
        self.python.touch()
        self.python.with_name('pythonw.exe').touch()
        self.patches = [
            mock.patch.object(windows_quota.sys, 'platform', 'win32'),
            mock.patch.object(windows_quota.sys, '_base_executable', str(self.python), create=True),
            mock.patch.object(windows_quota, 'CONFIG', self.config),
            mock.patch.object(windows_quota, 'UI', self.ui),
            mock.patch.object(windows_quota, 'programs_folder', return_value=self.folder),
            mock.patch.object(windows_quota, 'find_conflicts', return_value={'conflicts': [], 'unreadable': 0}),
            mock.patch.object(windows_quota.shutil, 'which', return_value=None),
            mock.patch.object(windows_quota, 'create_link', side_effect=self.create_link),
            mock.patch.object(windows_quota, 'read_link', side_effect=lambda path: json.loads(path.read_text())),
        ]
        for patch in self.patches:
            patch.start()
        self.addCleanup(self.cleanup_patches)

    def cleanup_patches(self):
        for patch in reversed(self.patches):
            patch.stop()
        self.tmp.cleanup()

    def create_link(self, path, pythonw, ui, key):
        info = {'target': str(pythonw), 'arguments': '"' + str(ui) + '"',
                'description': windows_quota.OWNER, 'hotkey': key}
        path.write_text(json.dumps(info))
        return info

    def test_dry_run_does_not_create_files(self):
        self.assertEqual(windows_quota.install(dry_run=True)['status'], 'DRY_RUN')
        self.assertFalse(self.config.exists())
        self.assertFalse(self.folder.exists())

    def test_conflict_and_unowned_shortcut_are_preserved(self):
        with mock.patch.object(windows_quota, 'find_conflicts', return_value={'conflicts': ['existing'], 'unreadable': 0}):
            with self.assertRaisesRegex(ValueError, '冲突'):
                windows_quota.install()
        self.folder.mkdir(parents=True)
        link = self.folder / 'Codex Quota.lnk'
        link.write_text('not ours')
        with self.assertRaisesRegex(ValueError, '拒绝覆盖'):
            windows_quota.install()
        self.assertEqual(link.read_text(), 'not ours')

    def test_install_update_verify_and_uninstall(self):
        self.assertEqual(windows_quota.install()['hotkey'], 'CTRL+ALT+Q')
        self.assertEqual(windows_quota.install('CTRL+SHIFT+Q')['hotkey'], 'CTRL+SHIFT+Q')
        self.assertEqual(windows_quota.verify()['configuredHotkey'], 'CTRL+SHIFT+Q')
        self.assertEqual(windows_quota.uninstall()['status'], 'UNINSTALLED')
        self.assertFalse(self.config.exists())
        self.assertFalse(self.folder.exists())

    def test_failed_update_restores_original_shortcut_and_config(self):
        windows_quota.install()
        link = self.folder / 'Codex Quota.lnk'
        original_link, original_config = link.read_bytes(), self.config.read_bytes()
        with mock.patch.object(windows_quota.os, 'replace', side_effect=OSError('synthetic failure')):
            with self.assertRaises(OSError):
                windows_quota.install('CTRL+SHIFT+Q')
        self.assertEqual(link.read_bytes(), original_link)
        self.assertEqual(self.config.read_bytes(), original_config)

    def test_modified_shortcut_is_not_deleted(self):
        windows_quota.install()
        link = self.folder / 'Codex Quota.lnk'
        info = json.loads(link.read_text())
        info['description'] = 'changed'
        link.write_text(json.dumps(info))
        with self.assertRaisesRegex(ValueError, '拒绝覆盖或删除'):
            windows_quota.uninstall()
        self.assertTrue(link.exists())
        self.assertTrue(self.config.exists())


@unittest.skipUnless(sys.platform == 'win32', 'requires Windows Shell')
class WindowsShellTests(unittest.TestCase):
    def test_temporary_shortcut_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            link = Path(directory) / 'Quota.lnk'
            pythonw = Path(sys.executable).with_name('pythonw.exe')
            self.assertTrue(pythonw.is_file())
            info = windows_quota.create_link(link, pythonw, windows_quota.UI, 'CTRL+ALT+Q')
            self.assertEqual(windows_quota.normalize_hotkey(info['hotkey']), 'CTRL+ALT+Q')
            actual = windows_quota.read_link(link)
            self.assertEqual(actual['description'], windows_quota.OWNER)
            self.assertEqual(Path(actual['target']).resolve(), pythonw.resolve())
            self.assertEqual(windows_quota.normalize_hotkey(actual['hotkey']), 'CTRL+ALT+Q')


if __name__ == '__main__':
    unittest.main()
