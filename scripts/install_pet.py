#!/usr/bin/env python3
"""Install a validated local pet; existing IDs require --replace and are backed up."""
import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile
from datetime import datetime, timezone
from uuid import uuid4

from petlib import reject_package_output, reject_symlink_chain, validate, write_json


def codex_home_path(codex_home=None):
    raw_home = codex_home or os.environ.get('CODEX_HOME') or str(Path.home() / '.codex')
    home = Path(raw_home).expanduser()
    if not home.is_absolute():
        raise ValueError('CODEX_HOME must be absolute')
    reject_symlink_chain(home)
    home = home.resolve()
    if home == Path(home.anchor) or home == Path.home().resolve():
        raise ValueError('CODEX_HOME must be a dedicated directory, not filesystem or user home root')
    return home


def install(package, codex_home=None, dry_run=False, replace=False):
    source = Path(package).absolute()
    reject_symlink_chain(source)
    source = source.resolve()
    validation = validate(source)
    if not validation['ok']:
        raise ValueError('; '.join(validation['errors']))
    home = codex_home_path(codex_home)
    pets = home / 'pets'
    reject_symlink_chain(pets)
    if pets.exists() and not pets.is_dir():
        raise ValueError('pets path is not a directory')
    target = pets / validation['pet_id']
    reject_symlink_chain(target)
    if target == source or source in target.parents or target in source.parents:
        raise ValueError('source and destination must be separate directories')
    if pets.exists():
        for child in pets.iterdir():
            if child.name.startswith('.') or child == target or not child.is_dir():
                continue
            candidate = child / 'pet.json'
            if child.is_symlink() or candidate.is_symlink():
                # Never traverse another pet's symlink.
                continue
            if candidate.is_file():
                try:
                    data = json.loads(candidate.read_text(encoding='utf-8'))
                except (OSError, ValueError):
                    continue
                if isinstance(data, dict) and data.get('id') == validation['pet_id']:
                    raise ValueError(f'duplicate manifest ID in another pet directory: {child.name}')
    if target.exists() and not target.is_dir():
        raise ValueError('target exists and is not a directory')
    if target.exists() and not replace:
        raise ValueError('ID exists; use --replace to back up first (or choose a new ID)')
    if target.exists():
        # Do not move directories containing links to personal files.
        for path in target.rglob('*'):
            if path.is_symlink():
                raise ValueError('existing target contains symlinks; refusing replacement')
    backup_root = home / 'pet-backups'
    reject_symlink_chain(backup_root)
    backup = backup_root / f"{validation['pet_id']}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}" if target.exists() else None
    result = {'ok': True, 'status': 'DRY_RUN' if dry_run else 'FILES_INSTALLED', 'target': str(target), 'backup': str(backup) if backup else None, 'pet_id': validation['pet_id'], 'manifest_sha256': validation['manifest_sha256'], 'spritesheet_sha256': validation['spritesheet_sha256'], 'gui_qa': 'MANUAL_GUI_CHECK_REQUIRED', 'warnings': validation['warnings']}
    if dry_run:
        return result
    pets.mkdir(parents=True, exist_ok=True)
    staging_root = Path(tempfile.mkdtemp(prefix='.atelier-install-', dir=pets))
    staging = staging_root / validation['pet_id']
    staging.mkdir()
    moved_old = False
    published_new = False
    try:
        for filename in ('pet.json', 'spritesheet.webp'):
            shutil.copyfile(source / filename, staging / filename)
        copied = validate(staging)
        if not copied['ok'] or any(copied.get(key) != validation[key] for key in ('manifest_sha256', 'spritesheet_sha256')):
            raise ValueError('copied package differs from validated source')
        if backup:
            backup_root.mkdir(parents=True, exist_ok=True)
            target.rename(backup)
            moved_old = True
        elif target.exists():
            raise ValueError('target appeared during installation; refusing overwrite')
        staging.rename(target)
        published_new = True
        installed = validate(target)
        if not installed['ok'] or any(installed.get(key) != validation[key] for key in ('manifest_sha256', 'spritesheet_sha256')):
            raise ValueError('installed package failed integrity check')
        result['installed_validation'] = installed
    except BaseException:
        if published_new and target.exists():
            shutil.rmtree(target)
        if moved_old and backup.exists():
            backup.rename(target)
        raise
    finally:
        shutil.rmtree(staging_root)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package')
    parser.add_argument('--codex-home')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--replace', action='store_true')
    parser.add_argument('--report')
    args = parser.parse_args()
    if args.report:
        try:
            reject_package_output(args.package, args.report)
            home = codex_home_path(args.codex_home)
            reject_package_output(home / 'pets', args.report)
            reject_package_output(home / 'pet-backups', args.report)
        except (ValueError, OSError) as exc:
            parser.exit(1, f'{exc}\n')
    try:
        result = install(args.package, args.codex_home, args.dry_run, args.replace)
    except (ValueError, OSError) as exc:
        result = {'ok': False, 'status': 'INSTALL_BLOCKED', 'error': str(exc)}
    if args.report:
        write_json(args.report, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
