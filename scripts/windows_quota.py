#!/usr/bin/env python3
"""Install a per-user Windows Shell shortcut for the on-demand quota window."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / 'windows' / 'quota_bubble.py'
CONFIG = ROOT / 'workruns' / 'windows-quota-config.json'
OWNER = 'Codex Pet Atelier Windows Quota v2.1'
DEFAULT_HOTKEY = 'CTRL+ALT+Q'


def normalize_hotkey(value):
    parts = value.replace(' ', '').upper().split('+')
    if len(parts) < 3 or len(set(parts)) != len(parts):
        raise ValueError('快捷键须包含两个或三个不同的修饰键，例如 CTRL+ALT+Q。')
    modifiers, key = set(parts[:-1]), parts[-1]
    if not modifiers <= {'CTRL', 'ALT', 'SHIFT'} or len(modifiers) not in (2, 3):
        raise ValueError('仅支持 CTRL、ALT、SHIFT 组合。')
    if not re.fullmatch(r'[A-Z0-9]|F(?:[1-9]|1[0-2])', key):
        raise ValueError('请选择字母、数字或 F1–F12。')
    return '+'.join([m for m in ('CTRL', 'ALT', 'SHIFT') if m in modifiers] + [key])


def powershell(script, values=None):
    executable = shutil.which('powershell.exe')
    if not executable:
        raise ValueError('未找到 Windows PowerShell，请在 Windows 本机检查系统组件。')
    env = os.environ.copy()
    env.update(values or {})
    program = "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $ErrorActionPreference='Stop'; " + script
    result = subprocess.run([executable, '-NoProfile', '-NonInteractive', '-Command', program],
                            env=env, capture_output=True, text=True, encoding='utf-8',
                            errors='replace', timeout=40,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise ValueError('Windows 快捷方式操作失败，请检查文件权限及 PowerShell 系统策略。')
    try:
        return json.loads(result.stdout.lstrip('\ufeff'))
    except json.JSONDecodeError as exc:
        raise ValueError('Windows 快捷方式返回了无法识别的结果。') from exc


def programs_folder():
    value = powershell("ConvertTo-Json -Compress ([Environment]::GetFolderPath('Programs'))")
    if not isinstance(value, str) or not value:
        raise ValueError('无法找到当前用户的开始菜单目录。')
    return Path(value) / 'Codex Pet Atelier'


def read_link(path):
    script = '''$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:CPA_LINK);
      ConvertTo-Json -Compress @{target=$s.TargetPath; arguments=$s.Arguments;
        description=$s.Description; hotkey=$s.Hotkey}'''
    return powershell(script, {'CPA_LINK': str(path)})


def create_link(path, pythonw, ui, hotkey):
    script = '''$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:CPA_LINK);
      $s.TargetPath=$env:CPA_PYTHONW; $s.Arguments='"'+$env:CPA_UI+'"';
      $s.WorkingDirectory=$env:CPA_ROOT; $s.Description=$env:CPA_OWNER;
      $s.Hotkey=$env:CPA_HOTKEY; $s.Save();
      ConvertTo-Json -Compress @{target=$s.TargetPath; arguments=$s.Arguments;
        description=$s.Description; hotkey=$s.Hotkey}'''
    return powershell(script, {'CPA_LINK': str(path), 'CPA_PYTHONW': str(pythonw),
                              'CPA_UI': str(ui), 'CPA_ROOT': str(ROOT),
                              'CPA_OWNER': OWNER, 'CPA_HOTKEY': hotkey})


def find_conflicts(hotkey, own_link):
    script = '''$shell=New-Object -ComObject WScript.Shell; $found=@(); $unreadable=0;
      $wanted=(($env:CPA_HOTKEY -split '\\+' | Sort-Object) -join '+');
      $roots=@('DesktopDirectory','Programs','CommonDesktopDirectory','CommonPrograms') |
        ForEach-Object {[Environment]::GetFolderPath($_)} | Where-Object {$_} | Select-Object -Unique;
      foreach($root in $roots) {
        Get-ChildItem -LiteralPath $root -Filter '*.lnk' -File -Recurse -ErrorAction SilentlyContinue |
          ForEach-Object {
            if ($_.FullName -ne $env:CPA_LINK) {
              try {
                $value=$shell.CreateShortcut($_.FullName).Hotkey;
                $parts=(($value -replace '\\s','').ToUpper() -split '\\+' | Sort-Object) -join '+';
                if ($value -and $parts -eq $wanted) {
                  $found+= $_.FullName
                }
              } catch { $unreadable++ }
            }
          }
      }
      ConvertTo-Json -Compress @{conflicts=@($found); unreadable=$unreadable}'''
    result = powershell(script, {'CPA_LINK': str(own_link), 'CPA_HOTKEY': hotkey})
    if not isinstance(result, dict) or not isinstance(result.get('conflicts'), list):
        raise ValueError('无法检查已有快捷方式冲突。')
    return result


def load_config(path=None):
    path = CONFIG if path is None else path
    if path.is_symlink():
        raise ValueError('配置文件不能是符号链接。')
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('owner') != OWNER or data.get('ui') != str(UI):
        raise ValueError('已有配置不属于此工具，拒绝修改。')
    return data


def owned_link(link, config):
    if link.is_symlink() or not link.is_file():
        raise ValueError('快捷方式不存在或是符号链接。')
    info = read_link(link)
    if (str(info.get('target', '')).casefold() != str(config['pythonw']).casefold()
            or info.get('arguments') != '"' + str(UI) + '"'
            or info.get('description') != OWNER):
        raise ValueError('快捷方式已被修改或不属于此工具，拒绝覆盖或删除。')
    return info


def install(hotkey=None, codex_cli=None, dry_run=False):
    if sys.platform != 'win32':
        raise ValueError('Windows 快捷方式只能在 Windows 本机安装。')
    previous = load_config() if CONFIG.exists() or CONFIG.is_symlink() else None
    folder = programs_folder()
    link = folder / 'Codex Quota.lnk'
    if previous and str(link).casefold() != str(previous.get('link', '')).casefold():
        raise ValueError('开始菜单路径已变化，请先检查原快捷方式。')
    if folder.is_symlink() or link.is_symlink():
        raise ValueError('快捷方式目录或文件不能是符号链接。')
    if link.exists():
        if not previous:
            raise ValueError('同名快捷方式已存在，拒绝覆盖。')
        owned_link(link, previous)
    key = normalize_hotkey(hotkey or (previous or {}).get('hotkey') or DEFAULT_HOTKEY)
    conflict_check = find_conflicts(key, link)
    if conflict_check['conflicts']:
        raise ValueError('快捷键与现有桌面或开始菜单快捷方式冲突；请使用 --hotkey 选择其他组合。')
    python = Path(getattr(sys, '_base_executable', sys.executable)).resolve()
    pythonw = python.with_name('pythonw.exe')
    if not python.is_file() or not pythonw.is_file():
        raise ValueError('未找到 Python 或 pythonw.exe，请安装包含 Tk 的 Python。')
    saved_cli = (previous or {}).get('codexCLI')
    saved_usable = saved_cli and Path(saved_cli).is_file()
    cli = codex_cli or (saved_cli if saved_usable else shutil.which('codex'))
    if cli and not Path(cli).is_file():
        raise ValueError('指定的 Codex CLI 路径不存在。')
    codex_home = os.environ.get('CODEX_HOME', (previous or {}).get('codexHome'))
    config = {'owner': OWNER, 'ui': str(UI), 'python': str(python), 'pythonw': str(pythonw),
              'codexCLI': str(Path(cli).resolve()) if cli else None,
              'codexHome': codex_home or None, 'hotkey': key, 'link': str(link)}
    if dry_run:
        return {'status': 'DRY_RUN', 'hotkey': key, 'cli_found': bool(cli)}
    folder_existed = folder.exists()
    folder.mkdir(parents=True, exist_ok=True)
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    config['createdFolder'] = (previous or {}).get('createdFolder', not folder_existed)
    backup = folder / ('.quota-' + uuid.uuid4().hex + '.bak')
    staged_copy = folder / ('.quota-' + uuid.uuid4().hex + '.tmp')
    config_tmp = CONFIG.parent / ('.quota-' + uuid.uuid4().hex + '.tmp')
    moved = False
    published = False
    try:
        with tempfile.TemporaryDirectory(prefix='codex-quota-link-') as temp:
            staged_link = Path(temp) / 'Codex Quota.lnk'
            info = create_link(staged_link, pythonw, UI, key)
            if normalize_hotkey(info.get('hotkey', '')) != key:
                raise ValueError('系统未接受该快捷键，请选择其他组合。')
            with config_tmp.open('x', encoding='utf-8') as stream:
                stream.write(json.dumps(config, ensure_ascii=False, indent=2) + '\n')
            with staged_link.open('rb') as source, staged_copy.open('xb') as target:
                shutil.copyfileobj(source, target)
            if link.exists():
                owned_link(link, previous)
                link.rename(backup)
                moved = True
            staged_copy.rename(link)
            published = True
            owned_link(link, config)
            os.replace(config_tmp, CONFIG)
    except BaseException as exc:
        if published and link.exists():
            try:
                owned_link(link, config)
            except ValueError as changed:
                raise ValueError(f'安装失败；快捷方式已变化，原文件保留在 {backup}，请手动检查。') from changed
            link.unlink()
        if moved and backup.exists():
            if link.exists() or link.is_symlink():
                raise ValueError(f'安装失败；原快捷方式保留在 {backup}，请手动恢复。') from exc
            backup.rename(link)
        raise
    finally:
        staged_copy.unlink(missing_ok=True)
        config_tmp.unlink(missing_ok=True)
    if moved:
        backup.unlink()
    return {'status': 'INSTALLED', 'hotkey': key, 'cli_found': bool(cli),
            'unreadableShortcuts': conflict_check.get('unreadable', 0)}


def uninstall():
    if sys.platform != 'win32':
        raise ValueError('Windows 快捷方式只能在 Windows 本机卸载。')
    config = load_config()
    link = programs_folder() / 'Codex Quota.lnk'
    if str(link).casefold() != str(config.get('link', '')).casefold():
        raise ValueError('开始菜单路径已变化，请先检查原快捷方式。')
    if link.exists() or link.is_symlink():
        owned_link(link, config)
        link.unlink()
    CONFIG.unlink()
    if config.get('createdFolder'):
        try:
            link.parent.rmdir()
        except OSError:
            pass
    return {'status': 'UNINSTALLED'}


def verify():
    if sys.platform != 'win32':
        raise ValueError('Windows 快捷方式只能在 Windows 本机检查。')
    config = load_config()
    link = programs_folder() / 'Codex Quota.lnk'
    if str(link).casefold() != str(config.get('link', '')).casefold():
        raise ValueError('开始菜单路径已变化，请检查原快捷方式。')
    info = owned_link(link, config)
    return {'status': 'INSTALLED', 'configuredHotkey': info.get('hotkey'),
            'cli_found': bool(config.get('codexCLI'))}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    item = sub.add_parser('install')
    item.add_argument('--hotkey', help='例如 CTRL+ALT+Q 或 CTRL+SHIFT+Q')
    item.add_argument('--codex-cli', help='本机 Codex CLI 的路径')
    item.add_argument('--dry-run', action='store_true')
    sub.add_parser('verify')
    sub.add_parser('uninstall')
    args = parser.parse_args(argv)
    try:
        result = (install(args.hotkey, args.codex_cli, args.dry_run) if args.command == 'install'
                  else verify() if args.command == 'verify' else uninstall())
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print('操作未完成：' + str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.command == 'install':
        print('仅检查可读的桌面和开始菜单快捷方式；其他程序和 AltGr 仍可能冲突，请实机测试。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
