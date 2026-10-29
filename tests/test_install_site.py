"""Checks for the release archive boundary and official install link."""
import hashlib
import io
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlsplit
from zipfile import ZipFile, ZipInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_install_site as site


def bundle(manifest=None, sprite=b'RIFFfakeWEBP', extra=None, symlink=False):
    package = 'blue-whale-maid-v17'
    manifest = manifest or {'id': package, 'displayName': '鲸鱼 Maid', 'description': '测试 & 伙伴',
                            'spritesheetPath': 'spritesheet.webp'}
    target = io.BytesIO()
    with ZipFile(target, 'w') as archive:
        archive.writestr(package + '/pet.json', json.dumps(manifest))
        entry = ZipInfo(package + '/spritesheet.webp')
        if symlink:
            entry.create_system = 3
            entry.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(entry, sprite)
        if extra:
            archive.writestr(extra, b'bad')
    return target.getvalue()


class InstallSiteTests(unittest.TestCase):
    def metadata(self, data, sprite=b'RIFFfakeWEBP'):
        with ZipFile(io.BytesIO(data)) as archive:
            manifest = archive.read('blue-whale-maid-v17/pet.json')
        return {'id': 'blue-whale-maid-v17', 'zipSha256': hashlib.sha256(data).hexdigest(),
                'spriteSha256': hashlib.sha256(sprite).hexdigest(),
                'manifestSha256': hashlib.sha256(manifest).hexdigest()}

    def test_uri_has_official_fields_and_correct_encoding(self):
        manifest = {'displayName': '鲸鱼 Maid', 'description': '测试 & 伙伴'}
        image = 'https://example.org/assets/v1.7.0/spritesheet.webp'
        uri = site.deep_link(manifest, image)
        parsed = urlsplit(uri)
        values = parse_qs(parsed.query)
        self.assertEqual((parsed.scheme, parsed.netloc, parsed.path), ('codex', 'pets', '/install'))
        self.assertEqual(set(values), {'name', 'description', 'imageUrl', 'spriteVersionNumber'})
        self.assertEqual(values['name'], ['鲸鱼 Maid'])
        self.assertEqual(values['description'], ['测试 & 伙伴'])
        self.assertEqual(values['imageUrl'], [image])
        self.assertEqual(values['spriteVersionNumber'], ['1'])

    def test_hash_traversal_symlink_and_role_mismatch_rejected(self):
        cases = [
            (bundle(), {'zipSha256': '0' * 64}, 'SHA-256'),
            (bundle(extra='../escape'), {}, 'member'),
            (bundle(symlink=True), {}, 'unsafe'),
            (bundle(manifest={'id': 'wrong', 'spritesheetPath': 'spritesheet.webp'}), {}, 'manifest'),
            (bundle(), {'spriteSha256': '0' * 64}, 'spritesheet SHA-256'),
            (bundle(), {'manifestSha256': '0' * 64}, 'manifest SHA-256'),
        ]
        for data, override, error in cases:
            with self.subTest(error=error), tempfile.TemporaryDirectory() as directory:
                pet = self.metadata(data)
                pet.update(override)
                with self.assertRaisesRegex(ValueError, error):
                    site.unpack_package(data, pet, Path(directory))

    def test_bad_webp_is_rejected_by_real_validator(self):
        data = bundle()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'invalid V1 spritesheet'):
                site.unpack_package(data, self.metadata(data), Path(directory))

    def test_output_and_version_are_guarded(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'already exists'):
                site.build(directory, release_dir=directory)
            with mock.patch.object(site, 'CATALOG', Path(directory) / 'catalog.json'):
                site.CATALOG.write_text(json.dumps({'version': 'v1.6.0', 'releaseBase': '', 'pets': []}))
                with self.assertRaisesRegex(ValueError, 'version'):
                    site.build(Path(directory) / 'site', release_dir=directory)


if __name__ == '__main__':
    unittest.main()
