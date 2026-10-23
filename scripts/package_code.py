#!/usr/bin/env python3
"""Build or inspect a deterministic MIT code-only toolkit ZIP; artwork is excluded."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
from zipfile import BadZipFile, ZipFile, ZipInfo, ZIP_DEFLATED

from audit_publication import LIMIT, inspect
from petlib import digest, reject_symlink_chain

PREFIX = 'codex-pet-atelier-code-1.4.0'
# Explicit file names only. New files require a reviewed change to this list.
FILES = (
    '.github/workflows/validate.yml', '.gitignore', 'AGENTS.md', 'CHANGELOG.md',
    'CODEX_PROMPT.md', 'README.md', 'START_HERE.md', 'LICENSE', 'ASSET_LICENSE.md', 'CREDITS.md',
    'characters/blue-whale-maid.md', 'characters/orange-scholar.md', 'characters/silver-dragon.md',
    'docs/ASSET_RIGHTS.md', 'docs/CHARACTER_SPECS.md', 'docs/CODE_ONLY_RELEASE.md',
    'docs/CONTRIBUTING.md', 'docs/INSTALLATION.md', 'docs/MANUAL_GUI_CHECKLIST.md',
    'docs/PRODUCTION.md', 'docs/PROJECT_PLAN.md', 'pets/.gitkeep', 'references/README.md',
    'requirements.txt', 'scripts/audit_motion.py', 'scripts/audit_publication.py',
    'scripts/clean_chroma.py', 'scripts/extract_companion_frames.py', 'scripts/install_pet.py',
    'scripts/package_code.py', 'scripts/package_release.py', 'scripts/petlib.py',
    'scripts/preview_pet.py', 'scripts/validate_pet.py', 'tests/test_chroma.py',
    'tests/test_code_package.py', 'tests/test_companion.py', 'tests/test_publication.py',
    'tests/test_tools.py',
)
NOTICE = (b'CODE-ONLY TOOLKIT\n'
          b'Project code and documentation: MIT; see LICENSE and ASSET_LICENSE.md.\n'
          b'Local build status does not establish GitHub publication.\n'
          b'Artwork rights: UNVERIFIED; no artwork redistribution permission is granted.\n'
          b'No pet images, GIFs, screenshots, private references, reports or Git database are included.\n')
METADATA = ('CODE_ONLY_NOTICE.txt', 'RC_MANIFEST.json', 'SHA256SUMS')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def manifest(payloads):
    return (json.dumps({'format': 'code-only-rc-1', 'license_status': 'MIT_CODE_AND_DOCS',
                       'publication_status': 'LOCAL_BUILD_NOT_PUBLISHED',
                       'files': [{'path': name, 'bytes': len(data), 'sha256': sha(data)}
                                 for name, data in sorted(payloads.items())]},
                      ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def checksums(payloads):
    return ''.join(f'{sha(data)}  {name}\n' for name, data in sorted(payloads.items())).encode('utf-8')


def check_archive(path):
    path = Path(path)
    reject_symlink_chain(path)
    expected = {f'{PREFIX}/{name}' for name in (*FILES, *METADATA)}
    with ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) != len(expected) or {entry.filename for entry in entries} != expected:
            raise ValueError('archive members must exactly match the code-only whitelist; duplicates forbidden')
        if archive.comment:
            raise ValueError('unexpected ZIP comment')
        payloads = {}
        for entry in entries:
            mode = entry.external_attr >> 16
            if (entry.create_system != 3 or not stat.S_ISREG(mode) or stat.S_IMODE(mode) != 0o644
                    or entry.flag_bits & 1 or entry.extra or entry.comment or entry.file_size > LIMIT):
                raise ValueError('nonregular, encrypted, oversized, or unexpected ZIP metadata')
            name = entry.filename[len(PREFIX)+1:]
            data = archive.read(entry)
            reasons = inspect(name, data)
            if reasons:
                raise ValueError(f'archive content rejected: {name}: {reasons}')
            payloads[name] = data
        if payloads.pop('CODE_ONLY_NOTICE.txt') != NOTICE:
            raise ValueError('missing code-only license and artwork notice')
        actual_manifest = payloads.pop('RC_MANIFEST.json')
        actual_checksums = payloads.pop('SHA256SUMS')
        base = {**payloads, 'CODE_ONLY_NOTICE.txt': NOTICE}
        if actual_manifest != manifest(base):
            raise ValueError('RC manifest/hash mismatch')
        if actual_checksums != checksums({**base, 'RC_MANIFEST.json': actual_manifest}):
            raise ValueError('SHA256SUMS mismatch')
    return {'ok': True, 'status': 'CODE_ONLY_ARCHIVE_VALIDATED', 'path': str(path),
            'sha256': digest(path), 'members': sorted(expected), 'files': len(entries),
            'license_status': 'MIT_CODE_AND_DOCS', 'public_released': False,
            'note': 'Exact whitelist and payload checks; execution, rights and remote publication require separate evidence.'}


def build(root, output):
    root, output = Path(root).absolute(), Path(output).absolute()
    reject_symlink_chain(root)
    reject_symlink_chain(output)
    if output.suffix.lower() != '.zip' or output.exists():
        raise ValueError('output must be a new .zip file; overwrite refused')
    payloads = {}
    for name in FILES:
        path = root / name
        reject_symlink_chain(path)
        if not path.is_file() or path.stat().st_size > LIMIT:
            raise ValueError(f'whitelisted regular file missing or oversized: {name}')
        data = path.read_bytes()
        reasons = inspect(name, data)
        if reasons:
            raise ValueError(f'code-only source rejected: {name}: {reasons}')
        payloads[name] = data
    payloads['CODE_ONLY_NOTICE.txt'] = NOTICE
    payloads['RC_MANIFEST.json'] = manifest(payloads)
    payloads['SHA256SUMS'] = checksums(payloads)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output.parent, prefix='.atelier-code-', delete=False) as stream:
        temporary = Path(stream.name)
    try:
        with ZipFile(temporary, 'w', compression=ZIP_DEFLATED, compresslevel=9) as archive:
            for name, data in sorted(payloads.items()):
                entry = ZipInfo(f'{PREFIX}/{name}', date_time=(1980, 1, 1, 0, 0, 0))
                entry.create_system = 3
                entry.external_attr = (stat.S_IFREG | 0o644) << 16
                entry.compress_type = ZIP_DEFLATED
                archive.writestr(entry, data, compress_type=ZIP_DEFLATED, compresslevel=9)
        check_archive(temporary)
        os.link(temporary, output)  # Atomic no-overwrite publication to a local filename only.
        result = check_archive(output)
        result['status'] = 'CODE_ONLY_RC_BUILT_LOCAL'
        return result
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default=Path(__file__).resolve().parents[1])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--output')
    mode.add_argument('--check', metavar='ZIP')
    args = parser.parse_args()
    try:
        result = check_archive(args.check) if args.check else build(args.root, args.output)
    except (ValueError, OSError, BadZipFile) as exc:
        parser.exit(1, f'{exc}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
