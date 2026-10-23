#!/usr/bin/env python3
"""Build a two-file ZIP only with hash-bound rights, visual, and GUI evidence."""
import argparse
import json
import os
from pathlib import Path
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED

from petlib import STATES, digest, reject_symlink_chain, validate


def verify_evidence(evidence_path, validation):
    evidence_path = Path(evidence_path).absolute()
    reject_symlink_chain(evidence_path)
    data = json.loads(evidence_path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('evidence must be an object')
    for key in ('pet_id', 'manifest_sha256', 'spritesheet_sha256'):
        if data.get(key) != validation[key]:
            raise ValueError(f'evidence {key} does not match package')
    rights = data.get('rights', {})
    if not isinstance(rights, dict):
        raise ValueError('rights must be an object')
    if rights.get('status') != 'VERIFIED' or rights.get('redistribution_allowed') is not True or rights.get('derivatives_allowed') is not True:
        raise ValueError('public redistribution and derivative rights must be VERIFIED')
    for key in ('license', 'source', 'confirmed_by'):
        if not isinstance(rights.get(key), str) or not rights[key].strip():
            raise ValueError(f'rights.{key} is required')
    for name in ('rights', 'visual_qa', 'gui_qa'):
        section = data.get(name, {})
        if not isinstance(section, dict):
            raise ValueError(f'{name} must be an object')
        if name != 'rights' and section.get('status') != 'PASS':
            raise ValueError(f'{name} must PASS')
        if name != 'rights' and (not isinstance(section.get('reviewer'), str) or not section['reviewer'].strip()):
            raise ValueError(f'{name}.reviewer required')
        if name in ('visual_qa', 'gui_qa') and section.get('rows') != {state: 'PASS' for state in STATES}:
            raise ValueError(f'{name}.rows must PASS all nine states')
        entries = section.get('evidence')
        if not isinstance(entries, list) or not entries:
            raise ValueError(f'{name} needs actual evidence files')
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get('path'), str):
                raise ValueError(f'{name} evidence entry must contain path and sha256')
            relative = Path(entry['path'])
            if relative.is_absolute() or '..' in relative.parts or '\\' in entry['path']:
                raise ValueError('evidence paths must be safe relative paths')
            target = evidence_path.parent / relative
            reject_symlink_chain(target)
            if not target.is_file() or digest(target) != entry.get('sha256'):
                raise ValueError(f'{name} evidence file missing or hash mismatch')
    return data


def package_release(package, evidence_path, output):
    package, output = Path(package).absolute(), Path(output).absolute()
    result = validate(package)
    if not result['ok']:
        raise ValueError('; '.join(result['errors']))
    verify_evidence(evidence_path, result)
    reject_symlink_chain(output)
    if output.suffix.lower() != '.zip':
        raise ValueError('output must end in .zip')
    if output.exists():
        raise ValueError('output exists; refusing overwrite')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix='.atelier-release-', suffix='.zip', dir=output.parent, delete=False) as stream:
        temporary = Path(stream.name)
    try:
        filenames = ('pet.json', 'spritesheet.webp')
        # Re-read bytes and bind them to approved hashes immediately before packaging.
        payloads = {name: (package / name).read_bytes() for name in filenames}
        import hashlib
        if hashlib.sha256(payloads['pet.json']).hexdigest() != result['manifest_sha256'] or hashlib.sha256(payloads['spritesheet.webp']).hexdigest() != result['spritesheet_sha256']:
            raise ValueError('package changed since validation')
        with ZipFile(temporary, 'w', ZIP_DEFLATED) as archive:
            for name in filenames:
                archive.writestr(f"{result['pet_id']}/{name}", payloads[name])
        with ZipFile(temporary) as archive:
            expected = [f"{result['pet_id']}/{name}" for name in filenames]
            if archive.namelist() != expected or archive.testzip() is not None:
                raise ValueError('ZIP integrity check failed')
        # Exclusive link is an atomic no-overwrite publish on the same filesystem.
        os.link(temporary, output)
        return {'ok': True, 'status': 'LOCAL_ZIP_CREATED', 'path': str(output), 'sha256': digest(output), 'members': expected, 'note': 'Evidence was checked for presence, hashes, and recorded approvals. Human truth and legal authority cannot be certified by code; no network publication occurred.'}
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package')
    parser.add_argument('--evidence', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(package_release(args.package, args.evidence, args.output), ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
