#!/usr/bin/env python3
"""Build a static install site from hash-pinned V1.7 release packages."""
import argparse
import hashlib
import html
import io
import json
from pathlib import Path
import re
import stat
import tempfile
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen
from zipfile import BadZipFile, ZipFile

from petlib import validate

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://l-zeus.github.io/codex-pet-atelier/'
CATALOG = ROOT / 'site/releases-v1.7.0.json'
REPO = 'https://github.com/L-zeus/codex-pet-atelier'
PET_IDS = {'blue-whale-maid-v17', 'orange-scholar-v17', 'silver-dragon-v17'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def unpack_package(data, pet, directory):
    if sha(data) != pet['zipSha256']:
        raise ValueError('release ZIP SHA-256 mismatch: ' + pet['id'])
    expected = {pet['id'] + '/pet.json', pet['id'] + '/spritesheet.webp'}
    with ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        if len(entries) != 2 or {e.filename for e in entries} != expected:
            raise ValueError('ZIP member names do not match the pinned package')
        for entry in entries:
            mode = entry.external_attr >> 16
            if (stat.S_IFMT(mode) not in (0, stat.S_IFREG) or entry.is_dir()
                    or entry.flag_bits & 1 or entry.file_size > 5 * 1024 * 1024):
                raise ValueError('unsafe ZIP member')
        manifest_bytes = archive.read(pet['id'] + '/pet.json')
        sprite = archive.read(pet['id'] + '/spritesheet.webp')
    if sha(sprite) != pet['spriteSha256']:
        raise ValueError('spritesheet SHA-256 mismatch: ' + pet['id'])
    if sha(manifest_bytes) != pet['manifestSha256']:
        raise ValueError('manifest SHA-256 mismatch: ' + pet['id'])
    manifest = json.loads(manifest_bytes)
    if (not isinstance(manifest, dict) or manifest.get('id') != pet['id']
            or manifest.get('spritesheetPath') != 'spritesheet.webp'):
        raise ValueError('release manifest does not match the pinned role')
    package = directory / pet['id']
    package.mkdir()
    (package / 'pet.json').write_bytes(manifest_bytes)
    (package / 'spritesheet.webp').write_bytes(sprite)
    result = validate(package)
    if not result['ok']:
        raise ValueError('invalid V1 spritesheet: ' + '; '.join(result['errors']))
    return manifest, sprite


def deep_link(manifest, image_url):
    values = {'name': manifest['displayName'], 'imageUrl': image_url,
              'description': manifest['description'], 'spriteVersionNumber': '1'}
    return 'codex://pets/install?' + urlencode(values, quote_via=quote)


def load_catalog():
    catalog = json.loads(CATALOG.read_text(encoding='utf-8'))
    if (catalog['version'] != 'v1.7.0'
            or catalog['releaseBase'] != REPO + '/releases/download/v1.7.0/'
            or len(catalog['pets']) != 3 or {p['id'] for p in catalog['pets']} != PET_IDS):
        raise ValueError('unexpected release version or role mapping')
    for pet in catalog['pets']:
        if (pet['zip'] != pet['id'] + '-v1.7.0.zip'
                or not all(re.fullmatch(r'[0-9a-f]{64}', pet[field]) for field in ('zipSha256', 'spriteSha256', 'manifestSha256'))):
            raise ValueError('invalid pinned release metadata')
    return catalog


def document(title, content, prefix):
    e = html.escape
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)} · Codex Pet Atelier</title><link rel="icon" href="data:,"><link rel="stylesheet" href="{prefix}styles.css"></head>
<body><header><a href="{prefix}"><strong>CODEX PET ATELIER</strong></a><a href="{REPO}">GitHub ↗</a></header>
<main>{content}</main><footer>独立社区作品，并非 OpenAI 官方产品。<br>
美术：Codex Pet Atelier / L-zeus，V1.7 动画由原作改编，<a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>。
<a href="{REPO}/releases/download/v1.7.0/ASSET_ATTRIBUTION.txt">署名与修改说明</a> ·
<a href="{REPO}/releases/tag/v1.7.0">V1.7 发行资源</a></footer></body></html>'''


def shortcut_hint():
    return f'''<aside class="shortcut-hint"><strong>查看额度</strong> · Mac ⌥Q · Windows Ctrl+Alt+Q
<p>先自行设置快捷键，可更换组合；Windows 功能需在本机验证。</p>
<a href="{REPO}/blob/main/docs/MACOS_QUOTA_HOTKEY.md">Mac 设置</a> ·
<a href="{REPO}/blob/main/docs/WINDOWS_QUOTA_HOTKEY.md">Windows 设置</a></aside>'''


def build(output, release_dir=None, base_url=BASE):
    parsed = urlsplit(base_url)
    if parsed.scheme != 'https' or not parsed.netloc or parsed.query or parsed.fragment or parsed.username:
        raise ValueError('base URL must be an absolute HTTPS directory')
    base_url = base_url.rstrip('/') + '/'
    catalog = load_catalog()
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError('output already exists; refusing to overwrite')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='atelier-site-', dir=output.parent) as temporary:
        temp = Path(temporary)
        site = temp / 'site'
        site.mkdir()
        (site / 'styles.css').write_bytes((ROOT / 'site/styles.css').read_bytes())
        records = []
        for pet in catalog['pets']:
            if release_dir:
                data = (Path(release_dir) / pet['zip']).read_bytes()
            else:
                request = Request(catalog['releaseBase'] + pet['zip'], headers={'User-Agent': 'codex-pet-atelier-site'})
                with urlopen(request, timeout=45) as response:
                    data = response.read(6 * 1024 * 1024)
            manifest, sprite = unpack_package(data, pet, temp)
            original_manifest = (temp / pet['id'] / 'pet.json').read_bytes()
            if (ROOT / 'site/manifests/v1.7.0' / pet['id'] / 'pet.json').read_bytes() != original_manifest:
                raise ValueError('checked-in manifest differs from the V1.7 release')
            asset_path = f"assets/v1.7.0/{pet['id']}/spritesheet.webp"
            destination = site / asset_path
            destination.parent.mkdir(parents=True)
            destination.write_bytes(sprite)
            (destination.parent / 'pet.json').write_bytes(original_manifest)
            records.append({'pet': pet, 'manifest': manifest, 'asset': asset_path,
                            'uri': deep_link(manifest, base_url + asset_path)})
        e = html.escape
        cards = []
        for record in records:
            pet, manifest = record['pet'], record['manifest']
            cards.append(f'''<article class="card"><div class="visual"><div class="portrait" role="img"
aria-label="{e(manifest['displayName'], quote=True)} 的待机图" style="background-image:url('{e(record['asset'], quote=True)}')"></div></div>
<h2>{e(manifest['displayName'])}</h2><p class="details">{e(manifest['description'])}</p>
<a class="button" href="install/{pet['id']}/">查看安装</a></article>''')
        intro = '<p class="eyebrow">YOUR COMPANION, IN MOTION</p><h1>选一位伙伴，<br>带进 Codex。</h1><p class="lead">三位角色、九种原生动画。选择角色并在 Codex 中打开安装流程。</p>' + shortcut_hint()
        (site / 'index.html').write_text(document('选择你的宠物', intro + '<div class="cards">' + ''.join(cards) + '</div>', ''), encoding='utf-8')
        for record in records:
            pet, manifest = record['pet'], record['manifest']
            image = '../../' + record['asset']
            zip_url = catalog['releaseBase'] + pet['zip']
            content = f'''<a href="../../">← 返回角色列表</a><div class="detail">
<div class="visual"><div class="portrait" role="img" aria-label="{e(manifest['displayName'], quote=True)} 的待机图" style="background-image:url('{e(image, quote=True)}')"></div></div>
<div><p class="eyebrow">V1.7 · CODEX NATIVE PET</p><h1>{e(manifest['displayName'])}</h1>
<p class="details">{e(manifest['description'])}</p><p><a class="button" href="{e(record['uri'], quote=True)}">Open in Codex ↗</a></p>
<p class="details">点击后允许浏览器打开 Codex，并在官方界面完成安装。应用中的名称及目录由客户端决定。</p>
{shortcut_hint()}
<p><a class="button secondary" href="{zip_url}">下载 ZIP 备用安装</a></p>
<p class="details">如果 Codex 打开后没有安装窗口，可能是该客户端尚未启用安装入口。可下载 ZIP，或按 <a href="{REPO}#校验和安装">README</a> 配置 Python 环境后，在项目目录执行 <code>.venv/bin/python scripts/install_release_pet.py {pet['id']}</code>（Windows 使用 <code>.venv/Scripts/python.exe</code>），再刷新宠物列表。</p>
<details><summary>无法打开？手动安装</summary><ol><li>下载<a href="{zip_url}">此角色的 V1.7 ZIP</a>，并对照 <a href="{catalog['releaseBase']}V1_7_SHA256SUMS.txt">SHA-256</a> 校验。</li>
<li>解压后将角色文件夹放入 Codex 的 pets 目录；已有同名目录请先备份。</li>
<li>在 Codex 设置中刷新并选择。<a href="{REPO}/blob/main/docs/INSTALLATION.md">详细说明</a></li></ol></details></div></div>'''
            target = site / 'install' / pet['id']
            target.mkdir(parents=True)
            (target / 'index.html').write_text(document(manifest['displayName'], content, '../../'), encoding='utf-8')
        site.rename(output)
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release-dir', help='directory containing the exact published V1.7 ZIP files')
    parser.add_argument('--output', default='workruns/v1_9-site')
    args = parser.parse_args()
    try:
        records = build(args.output, args.release_dir)
    except (ValueError, OSError, BadZipFile, json.JSONDecodeError) as exc:
        parser.exit(1, f'Site build failed: {exc}\n')
    for record in records:
        print(record['pet']['id'], record['pet']['spriteSha256'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
