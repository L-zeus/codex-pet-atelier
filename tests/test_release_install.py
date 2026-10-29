"""Offline checks for the pinned release fallback installer."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import install_release_pet


class Response:
    def __init__(self, data, url='https://example.test/pet'):
        self.data, self.url = data, url
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def geturl(self): return self.url
    def read(self, limit): return self.data[:limit]


class ReleaseInstallTests(unittest.TestCase):
    def test_download_checks_hash_and_https_redirect(self):
        data = b'synthetic'
        expected = hashlib.sha256(data).hexdigest()
        with mock.patch.object(install_release_pet, 'urlopen', return_value=Response(data)):
            self.assertEqual(install_release_pet.download('https://example.test/pet', expected), data)
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                install_release_pet.download('https://example.test/pet', '0' * 64)
        with mock.patch.object(install_release_pet, 'urlopen', return_value=Response(data, 'http://example.test/pet')):
            with self.assertRaisesRegex(ValueError, 'HTTPS'):
                install_release_pet.download('https://example.test/pet', expected)

    def test_changed_local_manifest_is_rejected_before_download(self):
        pet = {'id': 'first', 'manifestSha256': '0' * 64, 'spriteSha256': '1' * 64}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            target = root / 'site/manifests/v1.7.0/first/pet.json'
            target.parent.mkdir(parents=True)
            target.write_text('{}')
            with mock.patch.object(install_release_pet, 'ROOT', root), \
                 mock.patch.object(install_release_pet, 'download') as fetch:
                with self.assertRaisesRegex(ValueError, 'SHA-256'):
                    install_release_pet.prepare(pet, root)
                fetch.assert_not_called()

    def test_conflict_prevents_any_installation(self):
        pets = [
            {'id': 'first', 'manifestSha256': 'a', 'spriteSha256': 'b'},
            {'id': 'second', 'manifestSha256': 'c', 'spriteSha256': 'd'},
        ]
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory).resolve() / 'codex'
            target = home / 'pets/second'
            target.mkdir(parents=True)
            with mock.patch.object(install_release_pet, 'prepare', side_effect=lambda p, t, r: t / p['id']), \
                 mock.patch.object(install_release_pet, 'validate', return_value={'ok': False}), \
                 mock.patch.object(install_release_pet, 'install') as installer:
                with self.assertRaisesRegex(ValueError, '拒绝覆盖'):
                    install_release_pet.install_selected(pets, codex_home=str(home))
                self.assertEqual(installer.call_count, 1)
                self.assertTrue(installer.call_args.kwargs['dry_run'])

    def test_identical_existing_pet_is_untouched(self):
        pet = {'id': 'first', 'manifestSha256': 'a', 'spriteSha256': 'b'}
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory).resolve() / 'codex'
            (home / 'pets/first').mkdir(parents=True)
            existing = {'ok': True, 'manifest_sha256': 'a', 'spritesheet_sha256': 'b'}
            with mock.patch.object(install_release_pet, 'prepare', return_value=home / 'package'), \
                 mock.patch.object(install_release_pet, 'validate', return_value=existing), \
                 mock.patch.object(install_release_pet, 'install') as installer:
                result = install_release_pet.install_selected([pet], codex_home=str(home))
                self.assertEqual(result, [{'id': 'first', 'status': 'ALREADY_INSTALLED'}])
                installer.assert_not_called()

    def test_partial_failure_reports_completed_pet_and_can_be_retried(self):
        pets = [
            {'id': 'first', 'manifestSha256': 'a', 'spriteSha256': 'b'},
            {'id': 'second', 'manifestSha256': 'c', 'spriteSha256': 'd'},
        ]
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory).resolve() / 'codex'
            failed = False

            def fake_install(package, codex_home, dry_run=False):
                nonlocal failed
                if dry_run:
                    return {'status': 'DRY_RUN'}
                if package.name == 'second' and not failed:
                    failed = True
                    raise OSError('synthetic disk error')
                target = home / 'pets' / package.name
                target.mkdir(parents=True)
                (target / 'marker').write_text('preserve')
                return {'status': 'FILES_INSTALLED'}

            def existing(path):
                return {'ok': True, 'manifest_sha256': 'a', 'spritesheet_sha256': 'b'}

            with mock.patch.object(install_release_pet, 'prepare', side_effect=lambda p, t, r: t / p['id']), \
                 mock.patch.object(install_release_pet, 'validate', side_effect=existing), \
                 mock.patch.object(install_release_pet, 'install', side_effect=fake_install):
                with self.assertRaisesRegex(ValueError, 'first.*重新运行'):
                    install_release_pet.install_selected(pets, codex_home=str(home))
                self.assertEqual((home / 'pets/first/marker').read_text(), 'preserve')
                result = install_release_pet.install_selected(pets, codex_home=str(home))
                self.assertEqual(result, [{'id': 'first', 'status': 'ALREADY_INSTALLED'},
                                          {'id': 'second', 'status': 'FILES_INSTALLED'}])


if __name__ == '__main__':
    unittest.main()
