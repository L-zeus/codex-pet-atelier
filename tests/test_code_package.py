"""Local code-only archive acceptance using bounded temporary fixtures; no artwork."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from zipfile import ZipFile, ZIP_DEFLATED

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from package_code import FILES, PREFIX, build, check_archive


class CodePackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.source = self.root / 'source'
        for name in FILES:
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('Synthetic code-only archive fixture.\n', encoding='utf-8')
        self.output = self.root / 'candidate.zip'

    def tearDown(self):
        self.tmp.cleanup()

    def test_exact_allowlist_determinism_and_license_scope(self):
        (self.source / 'private').mkdir()
        (self.source / 'private/unlisted.txt').write_text('never include this')
        result = build(self.source, self.output)
        other = build(self.source, self.root / 'repeat.zip')
        self.assertEqual(result['sha256'], other['sha256'])
        with ZipFile(self.output) as archive:
            self.assertEqual(len(archive.namelist()), len(FILES)+3)
            self.assertFalse(any('/private/' in name or '/.git/' in name for name in archive.namelist()))
            manifest = json.loads(archive.read(f'{PREFIX}/RC_MANIFEST.json'))
            self.assertEqual(manifest['license_status'], 'MIT_CODE_AND_DOCS')
            self.assertEqual(manifest['publication_status'], 'LOCAL_BUILD_NOT_PUBLISHED')
            notice = archive.read(f'{PREFIX}/CODE_ONLY_NOTICE.txt')
            self.assertIn(b'Artwork is not included', notice)
            self.assertIn(f'{PREFIX}/LICENSE', archive.namelist())
            self.assertIn(f'{PREFIX}/ASSET_LICENSE.md', archive.namelist())
        with self.assertRaisesRegex(ValueError, 'overwrite refused'):
            build(self.source, self.output)

    def test_missing_or_symlinked_whitelist_file_refused(self):
        target = self.source / 'README.md'
        target.unlink()
        with self.assertRaisesRegex(ValueError, 'missing'):
            build(self.source, self.output)
        target.symlink_to(self.source / 'AGENTS.md')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            build(self.source, self.output)
        self.assertFalse(self.output.exists())

    def test_disguised_media_and_sensitive_payload_refused(self):
        for data in (b'GIF89a', ('sk-' + 'x'*32).encode()):
            (self.source / 'README.md').write_bytes(data)
            with self.subTest(data_type=data[:3]):
                with self.assertRaisesRegex(ValueError, 'source rejected'):
                    build(self.source, self.output)
                self.assertFalse(self.output.exists())

    def test_traversal_extra_and_duplicate_zip_members_refused(self):
        build(self.source, self.output)
        with ZipFile(self.output) as archive:
            entries = [(entry, archive.read(entry)) for entry in archive.infolist()]
        for name in ('../escape.txt', f'{PREFIX}/.git/config', entries[0][0].filename):
            bad = self.root / 'bad.zip'
            with ZipFile(bad, 'w') as archive:
                for entry, data in entries:
                    archive.writestr(entry, data)
                # A duplicate is deliberate malformed input, not a build warning.
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore', UserWarning)
                    archive.writestr(name, 'unlisted')
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, 'whitelist'):
                    check_archive(bad)

    def test_tampered_bytes_or_symlink_zip_entry_refused(self):
        build(self.source, self.output)
        with ZipFile(self.output) as archive:
            entries = [(entry, archive.read(entry)) for entry in archive.infolist()]
        for mode in ('content', 'symlink'):
            bad = self.root / f'{mode}.zip'
            with ZipFile(bad, 'w', compression=ZIP_DEFLATED) as archive:
                for entry, data in entries:
                    if entry.filename == f'{PREFIX}/README.md':
                        if mode == 'content':
                            data = b'Changed without updating manifest.\n'
                        else:
                            entry.external_attr = (0o120777 << 16)
                    archive.writestr(entry, data)
            with self.subTest(mode=mode):
                with self.assertRaisesRegex(ValueError, 'mismatch|nonregular'):
                    check_archive(bad)

    def test_output_symlink_refused(self):
        target = self.root / 'keep.txt'
        target.write_text('preserve')
        self.output.symlink_to(target)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            build(self.source, self.output)
        self.assertEqual(target.read_text(), 'preserve')


if __name__ == '__main__':
    unittest.main()
