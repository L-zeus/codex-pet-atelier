"""Synthetic contract fixtures only: these are not character art or animation QA."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from petlib import COUNTS, DURATIONS, STATES, digest, validate, write_json
from preview_pet import gif_bytes, preview
from install_pet import install
from package_release import package_release
from package_local import package_local, NOTICE as LOCAL_NOTICE
from audit_motion import audit


class ToolsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_tmp = tempfile.TemporaryDirectory()
        cls.fixture_root = Path(cls.fixture_tmp.name).resolve()
        cls.fixture = cls.fixture_root / 'test-pet'
        cls.fixture.mkdir()
        cls.manifest = {'id': 'test-pet', 'displayName': 'Synthetic test fixture', 'description': 'Not character art. Machine-contract test only.', 'spritesheetPath': 'spritesheet.webp'}
        write_json(cls.fixture / 'pet.json', cls.manifest)
        atlas = Image.new('RGBA', (1536, 1872))
        draw = ImageDraw.Draw(atlas)
        for row, count in enumerate(COUNTS):
            for col in range(count):
                x, y = col*192, row*208
                draw.rectangle((x+50, y+40, x+130, y+180), fill=(25+col*22, 40+row*20, 180, 255))
                draw.rectangle((x+65+col, y+55, x+75+col, y+75), fill=(245, 245, 245, 255))
        atlas.save(cls.fixture / 'spritesheet.webp', lossless=True, exact=True)

    @classmethod
    def tearDownClass(cls):
        cls.fixture_tmp.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.package = self.root / 'test-pet'
        shutil.copytree(self.fixture, self.package)

    def tearDown(self):
        self.tmp.cleanup()

    def change_image(self, callback):
        with Image.open(self.package / 'spritesheet.webp') as source:
            image = source.copy()
        image = callback(image) or image
        image.save(self.package / 'spritesheet.webp', lossless=True, exact=True)

    def change_manifest(self, **kwargs):
        data = copy.deepcopy(self.manifest)
        data.update(kwargs)
        write_json(self.package / 'pet.json', data)

    def assert_invalid(self, substring):
        result = validate(self.package)
        self.assertFalse(result['ok'])
        self.assertTrue(any(substring in error for error in result['errors']), result)

    def make_evidence(self):
        report = validate(self.package)
        evidence_file = self.root / 'synthetic-evidence.txt'
        evidence_file.write_text('SYNTHETIC TEST ONLY: not actual rights, visual, or GUI acceptance.', encoding='utf-8')
        reference = [{'path': evidence_file.name, 'sha256': digest(evidence_file)}]
        data = {key: report[key] for key in ('pet_id', 'manifest_sha256', 'spritesheet_sha256')}
        data['rights'] = {'status': 'VERIFIED', 'redistribution_allowed': True, 'derivatives_allowed': True, 'license': 'TEST ONLY', 'source': 'synthetic test fixture', 'confirmed_by': 'unittest fixture', 'evidence': reference}
        data['visual_qa'] = {'status': 'PASS', 'reviewer': 'synthetic test fixture', 'rows': {state: 'PASS' for state in STATES}, 'evidence': reference}
        data['gui_qa'] = {'status': 'PASS', 'reviewer': 'synthetic test fixture', 'rows': {state: 'PASS' for state in STATES}, 'evidence': reference}
        target = self.root / 'evidence.json'
        write_json(target, data)
        return target, data

    def test_valid_machine_contract(self):
        result = validate(self.package)
        self.assertTrue(result['ok'], result)
        self.assertEqual((result['used_cells'], result['unused_cells']), (57, 15))
        self.assertEqual(result['visual_qa'], 'NOT_EXECUTED')

    def test_private_zip_installs_without_claiming_release_approval(self):
        output = self.root / 'local.zip'
        result = package_local(self.package, output)
        self.assertEqual(result['status'], 'LOCAL_ONLY_RIGHTS_PENDING')
        self.assertFalse(result['public_release_approved'])
        second = self.root / 'second.zip'
        package_local(self.package, second)
        self.assertEqual(output.read_bytes(), second.read_bytes())
        with ZipFile(output) as archive:
            self.assertEqual(set(archive.namelist()), {
                'test-pet/pet.json', 'test-pet/spritesheet.webp',
                'LOCAL_ONLY_NOTICE.txt', 'LOCAL_MANIFEST.json'})
            self.assertEqual(archive.read('LOCAL_ONLY_NOTICE.txt'), LOCAL_NOTICE)
            receipt = json.loads(archive.read('LOCAL_MANIFEST.json'))
            self.assertEqual(receipt['rights'], 'UNVERIFIED')
            self.assertFalse(receipt['public_release_approved'])
            self.assertEqual(receipt['files']['test-pet/spritesheet.webp'],
                             digest(self.package / 'spritesheet.webp'))
            archive.extractall(self.root / 'unpacked')
        installed = install(self.root / 'unpacked/test-pet', self.root / 'isolated-codex')
        self.assertEqual(installed['status'], 'FILES_INSTALLED')
        self.assertEqual(installed['spritesheet_sha256'], receipt['files']['test-pet/spritesheet.webp'])
        with self.assertRaisesRegex(ValueError, 'overwrite'):
            package_local(self.package, output)

    def test_private_zip_refuses_broken_pet_or_source_output(self):
        with self.assertRaisesRegex(ValueError, 'outside package'):
            package_local(self.package, self.package / 'local.zip')
        self.change_manifest(id='wrong')
        output = self.root / 'broken.zip'
        with self.assertRaisesRegex(ValueError, 'directory name'):
            package_local(self.package, output)
        self.assertFalse(output.exists())

    def test_wrong_dimensions(self):
        self.change_image(lambda img: img.resize((1136, 1385)))
        self.assert_invalid('wrong size')

    def test_missing_alpha(self):
        self.change_image(lambda img: img.convert('RGB'))
        self.assert_invalid('alpha/RGBA')

    def test_empty_effective_frame(self):
        self.change_image(lambda img: img.paste((0, 0, 0, 0), (0, 0, 192, 208)))
        self.assert_invalid('empty effective frame')

    def test_dirty_unused_cell(self):
        self.change_image(lambda img: img.putpixel((7*192+20, 20), (255, 0, 0, 255)))
        self.assert_invalid('unused cell')

    def test_hidden_rgb_under_transparency(self):
        self.change_image(lambda img: img.putpixel((1, 1), (255, 0, 0, 0)))
        self.assert_invalid('hidden RGB')

    def test_identical_frames_rejected(self):
        def repeat(img):
            frame = img.crop((0, 0, 192, 208))
            for col in range(6):
                img.paste(frame, (col*192, 0))
        self.change_image(repeat)
        self.assert_invalid('identical frames')

    def test_translation_only_frames_rejected(self):
        def translated(img):
            frame = img.crop((0, 0, 192, 208))
            sprite = frame.crop(frame.getchannel('A').getbbox())
            img.paste((0, 0, 0, 0), (0, 0, 1536, 208))
            for col in range(6):
                img.paste(sprite, (col*192+45+col, 35))
        self.change_image(translated)
        self.assert_invalid('translation-only')

    def test_missing_required_field(self):
        data = dict(self.manifest)
        del data['description']
        write_json(self.package / 'pet.json', data)
        self.assert_invalid('description')

    def test_wrong_id(self):
        self.change_manifest(id='another-pet')
        self.assert_invalid('directory name')

    def test_invalid_manifest_type(self):
        write_json(self.package / 'pet.json', [])
        self.assert_invalid('object')

    def test_path_traversal_and_absolute_names(self):
        for path in ('../outside.webp', '/tmp/outside.webp', 'nested/spritesheet.webp', r'..\outside.webp', 'https://example.com/pet.webp'):
            with self.subTest(path=path):
                self.change_manifest(spritesheetPath=path)
                self.assert_invalid('relative basename')

    def test_symlink_source_refused(self):
        sprite = self.package / 'spritesheet.webp'
        external = self.root / 'external.webp'
        sprite.rename(external)
        sprite.symlink_to(external)
        self.assert_invalid('symlink')

    def test_png_disguised_as_webp(self):
        with Image.open(self.package / 'spritesheet.webp') as src:
            src.save(self.package / 'spritesheet.webp', format='PNG')
        self.assert_invalid('WebP bytes')

    def test_animated_webp_is_not_a_static_atlas(self):
        with Image.open(self.package / 'spritesheet.webp') as source:
            first = source.convert('RGBA')
        second = first.copy()
        second.putpixel((60, 60), (255, 0, 0, 255))
        first.save(self.package / 'spritesheet.webp', save_all=True, append_images=[second],
                   duration=[100, 100], lossless=True, exact=True)
        self.assert_invalid('single static image')

    def test_preview_actual_rows_and_official_timing(self):
        target = self.root / 'previews'
        result = preview(self.package, target)
        self.assertTrue(result['ok'])
        self.assertEqual(len(result['previews']), 9)
        self.assertTrue((target / 'contact-sheet.png').is_file())
        self.assertTrue((target / 'contact-sheet-dark.png').is_file())
        with Image.open(target / 'contact-sheet-dark.png') as sheet:
            self.assertEqual(sheet.getpixel((1535, 0)), (32, 38, 50))
        for state, count, timings in zip(STATES, COUNTS, DURATIONS):
            with Image.open(target / f'{state}.gif') as gif:
                self.assertEqual(gif.n_frames, count)
                actual = []
                for index in range(count):
                    gif.seek(index)
                    actual.append(gif.info['duration'])
                self.assertEqual(actual, list(timings))
        measured = audit(self.package, target)
        self.assertTrue(measured['ok'], measured)
        self.assertEqual(len(measured['rows']), 9)
        self.assertEqual(measured['visual_qa'], 'NOT_EXECUTED')
        self.assertTrue(measured['rows'][0]['transitions'][-1]['loop_seam'])
        self.assertEqual(len(measured['state_switches']), 72)
        self.assertTrue(all(row['gif']['atlas_decoded_frames_match'] for row in measured['rows']))
        (target / 'idle.gif').unlink()
        self.assertFalse(audit(self.package, target)['ok'])

    def test_preview_refuses_invalid_or_package_output(self):
        with self.assertRaises(ValueError):
            preview(self.package, self.package)
        self.change_manifest(id='wrong')
        with self.assertRaises(ValueError):
            preview(self.package, self.root / 'previews')

    def test_motion_rejects_wrong_gif_dimensions_and_loop(self):
        target = self.root / 'previews'
        preview(self.package, target)
        with Image.open(target / 'idle.gif') as gif:
            frames = []
            for index in range(gif.n_frames):
                gif.seek(index)
                frames.append(gif.convert('RGBA'))
        for size, loop in (((10, 10), 0), ((192, 208), 1)):
            images = [frame.resize(size) for frame in frames]
            images[0].save(target / 'idle.gif', save_all=True, append_images=images[1:],
                           duration=list(DURATIONS[0]), disposal=2, loop=loop)
            with self.subTest(size=size, loop=loop):
                self.assertFalse(audit(self.package, target)['ok'])

    def test_motion_rejects_reordered_gif_from_same_atlas(self):
        target = self.root / 'previews'
        preview(self.package, target)
        with Image.open(self.package / 'spritesheet.webp') as atlas:
            frames = [atlas.crop((col*192, 0, (col+1)*192, 208)) for col in range(6)]
        (target / 'idle.gif').write_bytes(gif_bytes(frames[::-1], DURATIONS[0]))
        measured = audit(self.package, target)
        self.assertFalse(measured['ok'])
        self.assertFalse(measured['rows'][0]['gif']['atlas_decoded_frames_match'])

    def test_preview_preflights_all_output_links_before_writing(self):
        original = digest(self.package / 'spritesheet.webp')
        for index, name in enumerate(('idle.gif', 'contact-sheet-dark.png', 'preview-report.json')):
            target = self.root / f'previews-{index}'
            target.mkdir()
            (target / name).symlink_to(self.package / 'spritesheet.webp')
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, 'symlink'):
                    preview(self.package, target)
                self.assertEqual(digest(self.package / 'spritesheet.webp'), original)
                self.assertEqual(len(list(target.iterdir())), 1)

    def test_preview_atomic_output_does_not_write_through_hardlink(self):
        target = self.root / 'previews'
        target.mkdir()
        source = self.package / 'spritesheet.webp'
        original = digest(source)
        os.link(source, target / 'idle.gif')
        preview(self.package, target)
        self.assertEqual(digest(source), original)
        self.assertTrue(validate(self.package)['ok'])
        self.assertFalse(os.path.samefile(source, target / 'idle.gif'))

    def test_dry_run_does_not_create_directories(self):
        home = self.root / 'codex-home'
        result = install(self.package, str(home), dry_run=True)
        self.assertEqual(result['status'], 'DRY_RUN')
        self.assertFalse(home.exists())

    def test_install_respects_codex_home_and_preserves_other_pet(self):
        home = self.root / 'codex-home'
        other = home / 'pets' / 'other-pet'
        other.mkdir(parents=True)
        (other / 'note').write_text('keep me')
        with patch.dict(os.environ, {'CODEX_HOME': str(home)}):
            result = install(self.package)
        self.assertEqual(result['gui_qa'], 'MANUAL_GUI_CHECK_REQUIRED')
        self.assertEqual(digest(home / 'pets/test-pet/spritesheet.webp'), digest(self.package / 'spritesheet.webp'))
        self.assertEqual((other / 'note').read_text(), 'keep me')

    def test_duplicate_id_refused_and_explicit_replace_backed_up(self):
        home = self.root / 'codex-home'
        installed = install(self.package, str(home))
        target = Path(installed['target'])
        (target / 'preserve.txt').write_text('old local pet data')
        with self.assertRaisesRegex(ValueError, 'ID exists'):
            install(self.package, str(home))
        result = install(self.package, str(home), replace=True)
        self.assertEqual((Path(result['backup']) / 'preserve.txt').read_text(), 'old local pet data')
        self.assertTrue(validate(target)['ok'])
        self.assertFalse((target / 'preserve.txt').exists())

    def test_duplicate_manifest_id_in_other_directory_refused(self):
        home = self.root / 'codex-home'
        other = home / 'pets' / 'different-directory'
        other.mkdir(parents=True)
        write_json(other / 'pet.json', self.manifest)
        with self.assertRaisesRegex(ValueError, 'duplicate manifest ID'):
            install(self.package, str(home))

    def test_destination_symlink_refused(self):
        home = self.root / 'codex-home'
        home.mkdir()
        (home / 'pets').symlink_to(self.root / 'elsewhere')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            install(self.package, str(home))

    def test_install_relative_home_refused(self):
        with self.assertRaisesRegex(ValueError, 'absolute'):
            install(self.package, 'relative-home')

    def test_existing_pet_with_symlink_not_moved(self):
        home = self.root / 'codex-home'
        install(self.package, str(home))
        target = home / 'pets/test-pet'
        (target / 'linked-note').symlink_to(self.root / 'personal-note')
        with self.assertRaisesRegex(ValueError, 'symlinks'):
            install(self.package, str(home), replace=True)
        self.assertTrue((target / 'linked-note').is_symlink())

    def test_install_failure_restores_backup(self):
        home = self.root / 'codex-home'
        install(self.package, str(home))
        target = home / 'pets/test-pet'
        (target / 'keep.txt').write_text('previous pet')
        real_validate = validate
        calls = []
        def check(path):
            calls.append(str(path))
            result = real_validate(path)
            if len(calls) == 3:
                result['ok'] = False
            return result
        with patch('install_pet.validate', side_effect=check):
            with self.assertRaisesRegex(ValueError, 'integrity'):
                install(self.package, str(home), replace=True)
        self.assertEqual((target / 'keep.txt').read_text(), 'previous pet')

    def test_package_unknown_rights_blocked(self):
        path, data = self.make_evidence()
        data['rights']['status'] = 'UNVERIFIED'
        write_json(path, data)
        with self.assertRaisesRegex(ValueError, 'rights'):
            package_release(self.package, path, self.root / 'release.zip')
        self.assertFalse((self.root / 'release.zip').exists())

    def test_package_wrong_binding_blocked(self):
        path, data = self.make_evidence()
        data['spritesheet_sha256'] = '0'*64
        write_json(path, data)
        with self.assertRaisesRegex(ValueError, 'does not match'):
            package_release(self.package, path, self.root / 'release.zip')

    def test_package_gui_basic_pass_allows_untriggered_states(self):
        path, data = self.make_evidence()
        data['gui_qa']['rows'] = {state: 'NOT_RUN' for state in STATES}
        data['gui_qa']['rows']['idle'] = 'PASS'
        data['gui_qa']['checks'] = {'load': 'PASS', 'display': 'PASS', 'movement': 'PASS'}
        write_json(path, data)
        result = package_release(self.package, path, self.root / 'release.zip')
        self.assertEqual(result['status'], 'LOCAL_ZIP_CREATED')

    def test_package_partial_gui_requires_basic_checks_and_no_failed_rows(self):
        path, data = self.make_evidence()
        data['gui_qa']['rows']['review'] = 'NOT_RUN'
        data['gui_qa']['checks'] = {'load': 'PASS', 'display': 'PASS', 'movement': 'PASS'}
        for key in ('load', 'display', 'movement'):
            changed = copy.deepcopy(data)
            changed['gui_qa']['checks'][key] = 'NOT_RUN'
            write_json(path, changed)
            with self.subTest(check=key), self.assertRaisesRegex(ValueError, 'gui_qa.checks'):
                package_release(self.package, path, self.root / 'release.zip')
        for status in ('FAIL', 'UNKNOWN'):
            changed = copy.deepcopy(data)
            changed['gui_qa']['rows']['review'] = status
            write_json(path, changed)
            with self.subTest(status=status), self.assertRaisesRegex(ValueError, 'gui_qa.rows'):
                package_release(self.package, path, self.root / 'release.zip')
        changed = copy.deepcopy(data)
        changed['rights']['status'] = 'UNVERIFIED'
        write_json(path, changed)
        with self.assertRaisesRegex(ValueError, 'rights'):
            package_release(self.package, path, self.root / 'release.zip')

    def test_package_missing_gui_and_visual_rows_blocked(self):
        path, data = self.make_evidence()
        for scope in ('gui_qa', 'visual_qa'):
            changed = copy.deepcopy(data)
            changed[scope]['status'] = 'NOT_EXECUTED'
            write_json(path, changed)
            with self.assertRaisesRegex(ValueError, 'must PASS'):
                package_release(self.package, path, self.root / 'release.zip')
        for scope in ('gui_qa', 'visual_qa'):
            for rows in (None, {state: 'PASS' for state in STATES if state != 'idle'}):
                changed = copy.deepcopy(data)
                changed[scope]['rows'] = rows
                write_json(path, changed)
                with self.subTest(scope=scope, rows=rows):
                    with self.assertRaisesRegex(ValueError, 'all nine'):
                        package_release(self.package, path, self.root / 'release.zip')

    def test_package_tampered_evidence_blocked(self):
        path, data = self.make_evidence()
        (self.root / 'synthetic-evidence.txt').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            package_release(self.package, path, self.root / 'release.zip')

    def test_malformed_evidence_sections_fail_cleanly(self):
        path, data = self.make_evidence()
        for name in ('rights', 'visual_qa', 'gui_qa'):
            for value in (None, [], 'PASS'):
                changed = copy.deepcopy(data)
                changed[name] = value
                write_json(path, changed)
                with self.subTest(name=name, value=value):
                    with self.assertRaisesRegex(ValueError, 'must be an object'):
                        package_release(self.package, path, self.root / 'release.zip')

    def test_home_root_refused_and_dot_paths_normalized(self):
        for home in ('/', str(Path.home())):
            with self.assertRaisesRegex(ValueError, 'dedicated directory'):
                install(self.package, home, dry_run=True)
        home = self.root / 'codex-home'
        alias = home / '..' / 'codex-home'
        result = install(self.package, str(alias), dry_run=True)
        self.assertEqual(Path(result['target']), home / 'pets/test-pet')
        alias_home = self.root / 'alias-home'
        alias_package = alias_home / 'pets/test-pet'
        shutil.copytree(self.package, alias_package)
        with self.assertRaisesRegex(ValueError, 'separate directories'):
            install(alias_package, str(alias_home / '..' / 'alias-home'), dry_run=True)

    def test_package_exact_two_file_layout_and_no_overwrite(self):
        path, data = self.make_evidence()
        (self.package / 'private-notes.txt').write_text('must never enter ZIP')
        target = self.root / 'release.zip'
        result = package_release(self.package, path, target)
        self.assertEqual(result['status'], 'LOCAL_ZIP_CREATED')
        with ZipFile(target) as archive:
            self.assertEqual(archive.namelist(), ['test-pet/pet.json', 'test-pet/spritesheet.webp'])
        with self.assertRaisesRegex(ValueError, 'exists'):
            package_release(self.package, path, target)

    def test_cli_nonzero_and_machine_report_on_failure(self):
        self.change_manifest(id='wrong')
        report = self.root / 'report.json'
        proc = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'scripts/validate_pet.py'), str(self.package), '--report', str(report)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertFalse(json.loads(report.read_text())['ok'])

    def test_cli_reports_cannot_overwrite_source_or_installation(self):
        scripts = Path(__file__).resolve().parents[1] / 'scripts'
        home = self.root / 'isolated-home'
        original = {name: digest(self.package / name) for name in ('pet.json', 'spritesheet.webp')}
        for tool, name, extra in [('validate_pet.py', 'pet.json', []),
                                   ('audit_motion.py', 'spritesheet.webp', []),
                                   ('install_pet.py', 'pet.json', ['--dry-run', '--codex-home', str(home)])]:
            with self.subTest(tool=tool):
                proc = subprocess.run([sys.executable, str(scripts / tool), str(self.package),
                                       '--report', str(self.package / name), *extra], capture_output=True, text=True)
                self.assertEqual(proc.returncode, 1)
                self.assertIn('outside package', proc.stderr)
                self.assertEqual({n: digest(self.package / n) for n in original}, original)
        for directory in ('pets', 'pet-backups'):
            report = home / directory / 'test-pet/pet.json'
            proc = subprocess.run([sys.executable, str(scripts / 'install_pet.py'), str(self.package),
                                   '--codex-home', str(home), '--report', str(report)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 1)
            self.assertFalse(home.exists())

    def test_json_report_atomic_write_preserves_hardlinked_manifest(self):
        source = self.package / 'pet.json'
        original = digest(source)
        output = self.root / 'report.json'
        os.link(source, output)
        write_json(output, {'synthetic_report': True})
        self.assertEqual(digest(source), original)
        self.assertEqual(json.loads(output.read_text()), {'synthetic_report': True})


if __name__ == '__main__':
    unittest.main()
