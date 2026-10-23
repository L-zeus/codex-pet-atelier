"""Code-only publication guardrail tests; temporary synthetic Git repositories."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from audit_publication import audit, inspect


class PublicationTests(unittest.TestCase):
    def test_private_media_and_disguised_binary_refused(self):
        for path, data in [('workruns/note.txt', b'private'), ('pets/demo/pet.json', b'{}'),
                           ('picture.webp', b'RIFF\x00'), ('renamed.txt', b'\xff\xd8\xff'),
                           ('.env', b'VALUE=test'), ('large.txt', b'x' * (1024*1024+1)),
                           ('pointer.txt', b'version https://git-lfs.github.com/spec/v1\n')]:
            with self.subTest(path=path):
                self.assertTrue(inspect(path, data))

    def test_sensitive_values_are_categories_only(self):
        samples = {'personal_absolute_path': '/' + 'Users' + '/example/private/',
                   'email_address': 'person' + '@' + 'example.org',
                   'private_key': '-----BEGIN ' + 'PRIVATE KEY-----',
                   'api_token': 'sk-' + 'a' * 32}
        for category, value in samples.items():
            with self.subTest(category=category):
                result = inspect('note.txt', value.encode())
                self.assertIn(category, result)
                self.assertNotIn(value, str(result))

    def test_safe_text_and_placeholders_allowed(self):
        self.assertEqual(inspect('README.md', b'Use $HOME and ${CODEX_HOME}.'), [])
        self.assertEqual(inspect('.env.example', b'KEY=replace-me'), [])
        self.assertEqual(inspect('pets/.gitkeep', b''), [])

    def test_removed_historical_media_still_found_and_ignored_files_not_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            def git(*args):
                return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.DEVNULL)
            git('init', '-q')
            (root / '.gitignore').write_text('private/\n')
            (root / 'README.md').write_text('Synthetic publication fixture.')
            (root / 'art.gif').write_bytes(b'GIF89a')
            git('add', '.')
            git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@localhost', 'commit', '-qm', 'fixture')
            git('rm', '-q', 'art.gif')
            git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@localhost', 'commit', '-qm', 'remove fixture')
            (root / 'private').mkdir()
            (root / 'private/ignored.txt').write_bytes(b'\xff')
            self.assertTrue(audit(root)['ok'])
            result = audit(root, history=True)
            self.assertFalse(result['ok'])
            self.assertTrue(any(f['scope'] == 'history' and f['path'] == 'art.gif' for f in result['findings']))
            self.assertFalse(any(r['path'].startswith('private/') for r in result['records']))

    def test_staged_sensitive_content_detected_even_after_worktree_cleaned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            path = root / 'note.txt'
            path.write_text('sk-' + 'b' * 32)
            subprocess.run(['git', '-C', str(root), 'add', 'note.txt'], check=True)
            path.write_text('safe working copy')
            result = audit(root)
            self.assertFalse(result['ok'])
            self.assertEqual(result['findings'][0]['scope'], 'index')


if __name__ == '__main__':
    unittest.main()
