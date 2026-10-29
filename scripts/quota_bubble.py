#!/usr/bin/env python3
"""Build, install, verify or remove the short-lived macOS quota panel."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = Path.home() / 'Library/Application Support/CodexPetAtelier/QuotaBubble'
MARKER = 'codex-pet-atelier-quota-bubble-v2'
SOURCE = ROOT / 'macos/QuotaBubble/main.swift'
FILES = (
    'QuotaBubble.app/Contents/Info.plist',
    'QuotaBubble.app/Contents/MacOS/QuotaBubble',
    'QuotaBubble.app/Contents/_CodeSignature/CodeResources',
    'codex_usage.py', 'show-quota-bubble',
)
EXTRA = {'config.json', 'installed.json'}
DIRECTORIES = {'QuotaBubble.app', 'QuotaBubble.app/Contents', 'QuotaBubble.app/Contents/MacOS',
               'QuotaBubble.app/Contents/_CodeSignature'}
LEGACY_FILES = set(FILES) - {'QuotaBubble.app/Contents/_CodeSignature/CodeResources'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_path(path):
    path = Path(path).expanduser().absolute()
    if path == Path.home() or path == Path(path.anchor):
        raise ValueError('安装目录不能是用户主目录或文件系统根目录。')
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError('安装路径不能包含符号链接。')
    return path


def inventory(root):
    found = set()
    directories = set()
    for path in root.rglob('*'):
        if path.is_symlink():
            raise ValueError('安装目录包含符号链接，拒绝修改。')
        if path.is_file():
            found.add(path.relative_to(root).as_posix())
        elif path.is_dir():
            directories.add(path.relative_to(root).as_posix())
    return found, directories


def verify(root, require_runtime=True):
    root = safe_path(root)
    info = json.loads((root / 'installed.json').read_text(encoding='utf-8'))
    files = set(info.get('files', {}))
    if info.get('owner') != MARKER or files not in (set(FILES), LEGACY_FILES):
        raise ValueError('安装标记不匹配。')
    directories = DIRECTORIES if files == set(FILES) else DIRECTORIES - {'QuotaBubble.app/Contents/_CodeSignature'}
    if inventory(root) != (files | EXTRA, directories):
        raise ValueError('安装目录包含未知或缺失文件，拒绝修改。')
    for name, expected in info['files'].items():
        if sha(root / name) != expected:
            raise ValueError('已安装文件发生变化，请先手动检查。')
    config = json.loads((root / 'config.json').read_text(encoding='utf-8'))
    if not isinstance(config.get('python'), str):
        raise ValueError('Python 配置无效。')
    if require_runtime and not Path(config['python']).is_file():
        raise ValueError('Python 路径不可用，请重新安装。')
    cli = config.get('codexCLI')
    if cli is not None and not isinstance(cli, str):
        raise ValueError('Codex CLI 配置无效。')
    if require_runtime and cli and (not Path(cli).is_file() or not os.access(cli, os.X_OK)):
        raise ValueError('Codex CLI 路径不可用，请重新安装。')
    if not os.access(root / 'show-quota-bubble', os.X_OK):
        raise ValueError('启动入口不可执行。')
    return {'installed': True, 'codex_cli_found': bool(cli), 'launcher': str(root / 'show-quota-bubble')}


def build(stage, python, codex_cli, codex_home, swiftc):
    stage.mkdir(mode=0o700)
    app = stage / 'QuotaBubble.app'
    contents = app / 'Contents'
    binary_dir = contents / 'MacOS'
    binary_dir.mkdir(parents=True)
    info = {'CFBundleName': 'Codex Quota', 'CFBundleDisplayName': 'Codex Quota',
            'CFBundleIdentifier': 'org.codexpetatelier.quota-bubble',
            'CFBundleExecutable': 'QuotaBubble', 'CFBundlePackageType': 'APPL',
            'CFBundleShortVersionString': '2.0', 'CFBundleVersion': '2',
            'LSUIElement': True, 'NSPrincipalClass': 'NSApplication'}
    with (contents / 'Info.plist').open('wb') as stream:
        plistlib.dump(info, stream)
    subprocess.run([swiftc, str(SOURCE), '-O', '-framework', 'AppKit',
                    '-o', str(binary_dir / 'QuotaBubble')], check=True)
    # Ad-hoc signing seals the local bundle without using a developer identity.
    signed = subprocess.run(['/usr/bin/codesign', '--force', '--sign', '-', '--timestamp=none', str(app)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if signed.returncode:
        raise ValueError('本地临时签名失败，请检查 macOS 签名工具或选择普通本机目录。')
    shutil.copyfile(ROOT / 'scripts/codex_usage.py', stage / 'codex_usage.py')
    launcher = stage / 'show-quota-bubble'
    launcher.write_text('#!/bin/sh\nfolder=$(/usr/bin/dirname "$0")\n'
                        'exec /usr/bin/open -g "$folder/QuotaBubble.app"\n', encoding='utf-8')
    launcher.chmod(0o700)
    config = {'python': str(python), 'codexCLI': str(codex_cli) if codex_cli else None,
              'codexHome': codex_home or None}
    config_path = stage / 'config.json'
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    config_path.chmod(0o600)
    metadata = {'owner': MARKER, 'files': {name: sha(stage / name) for name in FILES}}
    (stage / 'installed.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    verify(stage)


def install(root, cli=None, dry_run=False):
    if sys.platform != 'darwin':
        raise ValueError('原生气泡仅支持 macOS；其他平台可使用现有额度命令。')
    root = safe_path(root)
    previous_config = {}
    if root.exists():
        verify(root, require_runtime=False)
        previous_config = json.loads((root / 'config.json').read_text(encoding='utf-8'))
    swiftc = shutil.which('swiftc')
    if not swiftc:
        raise ValueError('未找到 Swift 编译器；请按 Apple 提示安装 Xcode Command Line Tools。')
    python = Path(sys.executable).resolve()
    saved_cli = previous_config.get('codexCLI')
    saved_cli_usable = saved_cli and Path(saved_cli).is_file() and os.access(saved_cli, os.X_OK)
    found = saved_cli if saved_cli_usable else (shutil.which('codex') or saved_cli)
    codex_cli = Path(cli or found).expanduser().resolve() if cli or found else None
    if codex_cli and (not codex_cli.is_file() or not os.access(codex_cli, os.X_OK)):
        raise ValueError('指定的 Codex CLI 不存在或不可执行。')
    codex_home = os.environ.get('CODEX_HOME', previous_config.get('codexHome'))
    if dry_run:
        return {'status': 'DRY_RUN', 'swift_available': True,
                'codex_cli_found': bool(codex_cli), 'launcher': str(root / 'show-quota-bubble')}
    root.parent.mkdir(parents=True, exist_ok=True)
    temp_root = Path(tempfile.mkdtemp(prefix='.quota-bubble-build-', dir=root.parent))
    stage = temp_root / 'QuotaBubble'
    backup = root.parent / ('.quota-bubble-backup-' + uuid.uuid4().hex)
    moved = False
    published = False
    try:
        build(stage, python, codex_cli, codex_home, swiftc)
        if root.exists():
            verify(root, require_runtime=False)
            root.rename(backup)
            moved = True
        stage.rename(root)
        published = True
        result = verify(root)
    except BaseException as exc:
        failed = None
        try:
            if published and (root.exists() or root.is_symlink()):
                failed = root.parent / ('.quota-bubble-failed-' + uuid.uuid4().hex)
                root.rename(failed)  # Preserve even unexpected files for inspection.
            if moved and backup.exists():
                if root.exists() or root.is_symlink():
                    raise OSError('安装目录已被其他文件占用')
                backup.rename(root)
        except OSError as recovery:
            raise ValueError(f'安装失败：{exc}；自动恢复未完成：{recovery}。旧版本保留在 {backup}。') from exc
        if failed:
            restored = '旧版本已恢复；' if moved else ''
            raise ValueError(f'安装失败：{exc}；{restored}未通过验证的候选保留在 {failed}。') from exc
        raise
    finally:
        shutil.rmtree(temp_root)
    if moved:
        try:
            verify(backup, require_runtime=False)
        except (OSError, ValueError, json.JSONDecodeError):
            result['warning'] = f'旧版本目录包含变动，已保留以供检查：{backup}'
        else:
            try:
                shutil.rmtree(backup)
            except OSError:
                result['warning'] = f'旧文件清理未完成，请检查：{backup}'
    result['status'] = 'INSTALLED'
    return result


def uninstall(root):
    root = safe_path(root)
    verify(root, require_runtime=False)
    shutil.rmtree(root)
    return {'status': 'UNINSTALLED'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('install', 'verify', 'uninstall'):
        item = sub.add_parser(name)
        item.add_argument('--install-dir', default=str(DEFAULT), help='辅助工具的专用目录')
        if name == 'install':
            item.add_argument('--dry-run', action='store_true')
            item.add_argument('--codex-cli', help='指定本机 Codex CLI 的绝对路径')
    args = parser.parse_args(argv)
    try:
        if args.command == 'install':
            result = install(args.install_dir, args.codex_cli, args.dry_run)
        elif args.command == 'verify':
            result = verify(args.install_dir)
        else:
            result = uninstall(args.install_dir)
    except (ValueError, OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        print('操作未完成：' + str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
