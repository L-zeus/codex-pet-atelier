#!/usr/bin/env python3
"""Archive a validated pet for private local use; this never approves public release."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

from petlib import digest, reject_package_output, validate

NOTICE = (
    'LOCAL ONLY — NOT A PUBLIC RELEASE\n'
    'Artwork source and derivative redistribution rights are UNVERIFIED.\n'
    'Do not upload this ZIP, its artwork or previews to GitHub or other public services.\n'
    'MIT covers project code and documentation only, not character artwork.\n'
    'Structure validation does not establish visual quality or native GUI playback.\n'
    'Install only the pet-id directory containing pet.json and spritesheet.webp.\n'
).encode('utf-8')


def package_local(package, output):
    package, output = Path(package).absolute(), Path(output).absolute()
    reject_package_output(package, output)
    if output.suffix.lower() != '.zip' or output.exists():
        raise ValueError('output must be a new .zip file; overwrite refused')
    validation = validate(package)
    if not validation['ok']:
        raise ValueError('; '.join(validation['errors']))
    payloads = {name: (package / name).read_bytes()
                for name in ('pet.json', 'spritesheet.webp')}
    for name, field in (('pet.json', 'manifest_sha256'),
                        ('spritesheet.webp', 'spritesheet_sha256')):
        if hashlib.sha256(payloads[name]).hexdigest() != validation[field]:
            raise ValueError('package changed since validation')
    pet_id = validation['pet_id']
    receipt = {
        'format': 'atelier-private-pet-1', 'pet_id': pet_id,
        'status': 'LOCAL_ONLY_RIGHTS_PENDING', 'rights': 'UNVERIFIED',
        'public_release_approved': False, 'machine_validation': 'PASS',
        'visual_qa': 'NOT_CERTIFIED_BY_PACKAGER', 'gui_qa': 'NOT_CERTIFIED_BY_PACKAGER',
        'files': {f'{pet_id}/{name}': hashlib.sha256(data).hexdigest()
                  for name, data in payloads.items()},
    }
    members = {f'{pet_id}/{name}': data for name, data in payloads.items()}
    members['LOCAL_ONLY_NOTICE.txt'] = NOTICE
    members['LOCAL_MANIFEST.json'] = (json.dumps(receipt, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output.parent, prefix='.atelier-local-', delete=False) as stream:
        temporary = Path(stream.name)
    try:
        with ZipFile(temporary, 'w', ZIP_DEFLATED, compresslevel=9) as archive:
            for name, data in sorted(members.items()):
                entry = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                entry.create_system = 3
                entry.external_attr = (stat.S_IFREG | 0o644) << 16
                archive.writestr(entry, data, compress_type=ZIP_DEFLATED, compresslevel=9)
        with ZipFile(temporary) as archive:
            if archive.namelist() != sorted(members) or archive.testzip() is not None:
                raise ValueError('ZIP integrity check failed')
            if any(archive.read(name) != data for name, data in members.items()):
                raise ValueError('ZIP payload differs from validated bytes')
        os.link(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return {'ok': True, 'status': receipt['status'], 'path': str(output),
            'sha256': digest(output), 'members': sorted(members),
            'public_release_approved': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        result = package_local(args.package, args.output)
    except (ValueError, OSError) as exc:
        parser.exit(1, f'{exc}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
