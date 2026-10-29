#!/usr/bin/env python3
"""Install hash-pinned V1.7 pets when the official deep-link dialog is unavailable."""
import argparse
import hashlib
from pathlib import Path
import sys
import tempfile
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from build_install_site import BASE, ROOT, PET_IDS, load_catalog, unpack_package
from install_pet import codex_home_path, install
from petlib import validate


def download(url, expected):
    request = Request(url, headers={'User-Agent': 'codex-pet-atelier-installer'})
    with urlopen(request, timeout=30) as response:
        if urlsplit(response.geturl()).scheme != 'https':
            raise ValueError('资源重定向不是 HTTPS。')
        data = response.read(5 * 1024 * 1024 + 1)
    if len(data) > 5 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('发行资源的 SHA-256 不匹配。')
    return data


def prepare(pet, temp, release_dir=None):
    if release_dir:
        data = (Path(release_dir) / pet['zip']).read_bytes()
        unpack_package(data, pet, temp)
        return temp / pet['id']
    base = BASE + 'assets/v1.7.0/' + pet['id'] + '/'
    manifest = (ROOT / 'site/manifests/v1.7.0' / pet['id'] / 'pet.json').read_bytes()
    if hashlib.sha256(manifest).hexdigest() != pet['manifestSha256']:
        raise ValueError('发行角色清单的 SHA-256 不匹配。')
    sprite = download(base + 'spritesheet.webp', pet['spriteSha256'])
    package = temp / pet['id']
    package.mkdir()
    (package / 'pet.json').write_bytes(manifest)
    (package / 'spritesheet.webp').write_bytes(sprite)
    result = validate(package)
    if not result['ok'] or result.get('pet_id') != pet['id']:
        raise ValueError('发行角色包验证失败。')
    return package


def install_selected(pets, release_dir=None, codex_home=None, dry_run=False):
    home = codex_home_path(codex_home)
    with tempfile.TemporaryDirectory(prefix='codex-pet-v17-') as tmp:
        temp = Path(tmp).resolve()
        prepared = [(pet, prepare(pet, temp, release_dir)) for pet in pets]
        pending, results = [], []
        # Check every target before writing any of them.
        for pet, package in prepared:
            target = home / 'pets' / pet['id']
            if target.exists() or target.is_symlink():
                if target.is_symlink():
                    raise ValueError('已有角色目录是符号链接，拒绝覆盖。')
                existing = validate(target)
                if (not existing['ok'] or existing.get('manifest_sha256') != pet['manifestSha256']
                        or existing.get('spritesheet_sha256') != pet['spriteSha256']):
                    raise ValueError('已有同名角色不同，拒绝覆盖：' + pet['id'])
                results.append({'id': pet['id'], 'status': 'ALREADY_INSTALLED'})
            else:
                install(package, codex_home, dry_run=True)
                pending.append((pet, package))
        for pet, package in pending:
            result = install(package, codex_home, dry_run=dry_run)
            results.append({'id': pet['id'], 'status': result['status']})
        return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pet', nargs='?', choices=sorted(PET_IDS))
    parser.add_argument('--all', action='store_true', help='安装三位角色')
    parser.add_argument('--dry-run', action='store_true', help='只检查，不安装')
    parser.add_argument('--release-dir', help='使用已下载的 V1.7 ZIP 目录')
    parser.add_argument('--codex-home', help='测试或自定义 Codex 目录')
    args = parser.parse_args()
    if bool(args.pet) == bool(args.all):
        parser.error('请指定一个角色 ID 或 --all。')
    try:
        catalog = load_catalog()
        pets = [pet for pet in catalog['pets'] if args.all or pet['id'] == args.pet]
        results = install_selected(pets, args.release_dir, args.codex_home, args.dry_run)
    except (OSError, ValueError) as exc:
        print('安装未完成：' + str(exc), file=sys.stderr)
        return 1
    for result in results:
        print(result['id'], result['status'])
    print('在 Codex 设置的 Pets 中刷新并选择角色。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
