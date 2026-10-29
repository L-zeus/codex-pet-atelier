#!/usr/bin/env python3
"""Read ChatGPT Codex rate limits once via the local official app-server."""
import argparse
from datetime import datetime, timezone
import html
import json
import math
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import webbrowser

SOURCE = 'Codex App Server account/rateLimits/read'
USAGE_URL = 'https://chatgpt.com/codex/settings/usage'
ROOT = Path(__file__).resolve().parents[1]


class UsageError(Exception):
    def __init__(self, status, message):
        self.status = status
        super().__init__(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def normalize(result):
    """Keep only the documented fields needed by the display, never account details."""
    if not isinstance(result, dict):
        raise UsageError('protocol_error', '额度响应格式不兼容。')
    by_id = result.get('rateLimitsByLimitId')
    if isinstance(by_id, dict) and by_id:
        items = list(by_id.items())
    else:
        single = result.get('rateLimits')
        items = [(single.get('limitId') or 'codex', single)] if isinstance(single, dict) else []
    buckets = []
    for key, bucket in items:
        if not isinstance(bucket, dict):
            continue
        windows = []
        for kind in ('primary', 'secondary'):
            window = bucket.get(kind)
            if not isinstance(window, dict):
                continue
            used = window.get('usedPercent')
            used = used if number(used) and used >= 0 else None
            duration = window.get('windowDurationMins')
            duration = duration if number(duration) and duration > 0 else None
            reset = window.get('resetsAt')
            reset = reset if number(reset) and 0 <= reset <= 253402300799 else None
            windows.append({'kind': kind, 'durationMins': duration, 'usedPercent': used,
                            'remainingPercent': max(0, min(100, 100 - used)) if used is not None else None,
                            'resetsAt': reset})
        credits = bucket.get('credits')
        safe_credits = None
        if isinstance(credits, dict):
            safe_credits = {}
            for field in ('hasCredits', 'unlimited'):
                if isinstance(credits.get(field), bool):
                    safe_credits[field] = credits[field]
            balance = credits.get('balance')
            if (isinstance(balance, str) and len(balance) <= 64 and balance.replace('.', '', 1).isdigit()) or number(balance):
                safe_credits['balance'] = balance
            if not safe_credits:
                safe_credits = None
        ident = bucket.get('limitId') or key
        name = bucket.get('limitName')
        reached = bucket.get('rateLimitReachedType')
        buckets.append({'id': str(ident)[:128], 'name': name[:128] if isinstance(name, str) else None,
                        'windows': windows, 'credits': safe_credits,
                        'rateLimitReachedType': reached[:128] if isinstance(reached, str) else None})
    resets = result.get('rateLimitResetCredits')
    count = resets.get('availableCount') if isinstance(resets, dict) else None
    count = count if isinstance(count, int) and not isinstance(count, bool) and count >= 0 else None
    return {'status': 'ok' if any(b['windows'] for b in buckets) else 'unavailable',
            'fetchedAt': now(), 'source': SOURCE, 'buckets': buckets,
            'resetCreditsAvailable': count,
            'ordinaryUsageAllowed': result.get('ordinaryUsageAllowed') if isinstance(result.get('ordinaryUsageAllowed'), bool) else None,
            'message': None if any(b['windows'] for b in buckets) else '账户未返回额度窗口。'}


def _reader(stream, output):
    try:
        for line in stream:
            output.put(line)
    finally:
        output.put(None)


def _read_diagnostics(stream, diagnostics):
    # Retain only a known startup category, never raw stderr or account details.
    for line in stream:
        if 'failed to initialize sqlite state runtime' in line.lower():
            diagnostics.add('state_runtime')
        if line.startswith('Error:') and ('operation not permitted' in line.lower() or 'permission denied' in line.lower()):
            diagnostics.add('permission_denied')


def _send(proc, value):
    try:
        proc.stdin.write(json.dumps(value, separators=(',', ':')) + '\n')
        proc.stdin.flush()
    except (BrokenPipeError, OSError) as exc:
        raise UsageError('protocol_error', 'App Server 提前退出。') from exc


def _receive(lines, request_id, deadline):
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise UsageError('timeout', 'App Server 响应超时。')
        try:
            line = lines.get(timeout=remaining)
        except queue.Empty as exc:
            raise UsageError('timeout', 'App Server 响应超时。') from exc
        if line is None:
            raise UsageError('protocol_error', 'App Server 提前退出。')
        try:
            message = json.loads(line)
        except (json.JSONDecodeError, UnicodeError) as exc:
            raise UsageError('protocol_error', 'App Server 返回了无效的 JSON。') from exc
        if not isinstance(message, dict):
            raise UsageError('protocol_error', 'App Server 响应格式不兼容。')
        if message.get('id') != request_id or 'method' in message:
            continue
        if 'error' in message:
            error = message.get('error')
            code = error.get('code') if isinstance(error, dict) else None
            status = 'protocol_error' if code in (-32600, -32601, -32602) else 'error'
            raise UsageError(status, 'App Server 拒绝了请求；请检查登录状态及 CLI 版本。')
        if not isinstance(message.get('result'), dict):
            raise UsageError('protocol_error', 'App Server 响应缺少结果。')
        return message['result']


def fetch_usage(timeout=15, executable=None):
    executable = executable or shutil.which('codex')
    if not executable:
        raise UsageError('cli_missing', '未找到 Codex CLI，请先安装。')
    try:
        proc = subprocess.Popen([executable, 'app-server'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace',
                                bufsize=1)
    except OSError as exc:
        raise UsageError('cli_missing', '无法启动 Codex CLI。') from exc
    lines = queue.Queue()
    diagnostics = set()
    reader = threading.Thread(target=_reader, args=(proc.stdout, lines), daemon=True)
    stderr_reader = threading.Thread(target=_read_diagnostics, args=(proc.stderr, diagnostics), daemon=True)
    reader.start()
    stderr_reader.start()
    deadline = time.monotonic() + timeout
    failure = None
    try:
        _send(proc, {'id': 1, 'method': 'initialize', 'params': {'clientInfo': {
            'name': 'codex_pet_atelier', 'title': 'Codex Pet Atelier', 'version': '1.8.0'}}})
        _receive(lines, 1, deadline)
        _send(proc, {'method': 'initialized', 'params': {}})
        _send(proc, {'id': 2, 'method': 'account/read', 'params': {'refreshToken': False}})
        account_result = _receive(lines, 2, deadline)
        account = account_result.get('account')
        if account is None:
            raise UsageError('auth_required', 'Codex CLI 未登录 ChatGPT，请使用官方登录流程。')
        if not isinstance(account, dict):
            raise UsageError('protocol_error', 'App Server 账户响应格式不兼容。')
        if account.get('type') in ('apiKey', 'amazonBedrock'):
            raise UsageError('auth_required', '当前 CLI 不是 ChatGPT 登录，无法读取套餐额度。')
        _send(proc, {'id': 3, 'method': 'account/rateLimits/read'})
        result = normalize(_receive(lines, 3, deadline))
    except UsageError as exc:
        failure = exc
    finally:
        try:
            proc.stdin.close()
        except OSError:
            pass
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        reader.join(timeout=1)
        stderr_reader.join(timeout=1)
        proc.stdout.close()
        proc.stderr.close()
    if failure:
        if 'state_runtime' in diagnostics:
            raise UsageError('error', 'App Server 无法初始化本地状态数据库；请检查本机权限或在常规终端运行。') from failure
        if 'permission_denied' in diagnostics:
            raise UsageError('error', 'App Server 启动受到系统权限限制；请在有权限的常规终端运行。') from failure
        raise failure
    return result


def write_snapshot(path, snapshot):
    # Local-only snapshots live under the repository's ignored workruns directory.
    directory = ROOT / 'workruns'
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError('快照路径不能包含符号链接。')
    path = path.resolve()
    directory = directory.resolve()
    if path == directory or directory not in path.parents:
        raise ValueError('快照只能写入本项目被忽略的 workruns/ 目录。')
    if path.suffix.lower() != '.json':
        raise ValueError('快照文件必须使用 .json 扩展名。')
    for parent in (path.parent, *path.parent.parents):
        if parent == directory:
            break
        if (parent / 'pet.json').exists() or (parent / 'spritesheet.webp').exists():
            raise ValueError('不能在宠物资源包中写入快照。')
    if path.exists():
        try:
            if not path.is_file() or path.stat().st_size > 1048576:
                raise ValueError()
            previous = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(previous, dict) or previous.get('source') != SOURCE:
                raise ValueError()
        except (OSError, UnicodeError, ValueError) as exc:
            raise ValueError('拒绝覆盖非本工具创建的快照。') from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.usage-', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(snapshot, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        os.replace(temporary, path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def display_time(stamp):
    if stamp is None:
        return '未提供'
    try:
        return datetime.fromtimestamp(stamp, timezone.utc).astimezone().strftime('%Y-%m-%d %H:%M:%S %Z %z')
    except (ValueError, OSError, OverflowError):
        return '未提供'


def window_label(minutes):
    if minutes == 300:
        return '5 小时'
    if minutes == 10080:
        return '每周'
    return f'{minutes:g} 分钟' if minutes is not None else '窗口时长未提供'


def render_html(snapshot):
    """A self-contained static snapshot; untrusted values are text, never markup."""
    esc = lambda value: html.escape(str(value), quote=True)
    fetched = snapshot.get('fetchedAt')
    try:
        fetched_time = datetime.fromisoformat(fetched.replace('Z', '+00:00'))
        if fetched_time.tzinfo is None:
            raise ValueError('timestamp lacks timezone')
        local_time = fetched_time.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z %z')
        stale = (datetime.now(timezone.utc) - fetched_time).total_seconds() > 3600
    except (AttributeError, ValueError, OverflowError):
        local_time, stale = '未提供', True
    windows = [w for b in snapshot.get('buckets', []) for w in b.get('windows', [])]
    stale = stale or any(w.get('resetsAt') is not None and w['resetsAt'] <= time.time() for w in windows)
    state = '已过期，请重新运行命令' if stale else '生成时为最新读取'
    permission = snapshot.get('ordinaryUsageAllowed')
    permission_text = {True: '允许正常使用', False: '不允许正常使用', None: '正常使用许可状态未提供'}[permission]
    sections = []
    for bucket in snapshot.get('buckets', []):
        title = bucket.get('name') or bucket.get('id') or '未命名额度桶'
        bucket_id = bucket.get('id') or '未提供'
        parts = [f'<section><h2>{esc(title)}</h2><p class="muted">额度桶：{esc(bucket_id)}</p>']
        if bucket.get('rateLimitReachedType'):
            parts.append(f'<p>服务端限制状态：{esc(bucket["rateLimitReachedType"])}</p>')
        for window in bucket.get('windows', []):
            used, remaining = window.get('usedPercent'), window.get('remainingPercent')
            used_text = f'{used:g}%' if number(used) else '未提供'
            remaining_text = f'{remaining:g}%' if number(remaining) else '未提供'
            bar = f'<progress max="100" value="{remaining:g}">{remaining_text}</progress>' if number(remaining) else ''
            parts.append(f'<div class="window"><div class="row"><strong>{esc(window_label(window.get("durationMins")))}</strong>'
                         f'<strong>剩余 {esc(remaining_text)}</strong></div>{bar}'
                         f'<p>已使用 {esc(used_text)} · 重置 {esc(display_time(window.get("resetsAt")))}</p></div>')
        credits = bucket.get('credits')
        if credits:
            parts.append('<p class="muted">额外积分：' + esc(json.dumps(credits, ensure_ascii=False)) + '</p>')
        sections.append(''.join(parts) + '</section>')
    count = snapshot.get('resetCreditsAvailable')
    reset_info = f'<p>可用额度重置次数：{esc(count)}</p>' if count is not None else ''
    message = f'<p class="notice">{esc(snapshot["message"])}</p>' if snapshot.get('message') else ''
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Codex Usage</title><style>
:root{{color-scheme:light; font-family:system-ui,-apple-system,sans-serif; color:#29263c; background:#f5f3f8}}
body{{margin:0; padding:clamp(18px,5vw,60px)}}main{{max-width:640px; margin:auto; background:#fff; border:1px solid #e7e3ed; border-radius:20px; padding:clamp(22px,5vw,40px); box-shadow:0 15px 45px #3a2d4410}}
h1{{margin:0 0 8px;font-size:2rem}}h2{{font-size:1.1rem;margin:0}}p{{line-height:1.55}}section{{border-top:1px solid #ebe8ef;padding:22px 0 0;margin-top:22px}}
.muted,small{{color:#6e697b}}.row{{display:flex;justify-content:space-between;gap:16px}}.window{{margin-top:20px}}.window p{{margin:6px 0;color:#6e697b;font-size:.92rem}}
progress{{display:block;width:100%;height:12px;margin-top:10px;accent-color:#8876a7}}.notice{{padding:12px;background:#f7f1e9;border-radius:8px}}a{{color:#594777}}code{{overflow-wrap:anywhere}}
</style></head><body><main><h1>Codex Usage</h1><p class="muted">本机私有快照 · {esc(state)}</p>
<p>{esc(permission_text)}。剩余比例不代表可发送的消息数，也不保证可继续使用。</p>{message}
{''.join(sections)}{reset_info}<section><p>更新时间：{esc(local_time)}<br>数据来源：{esc(snapshot.get('source', SOURCE))}</p>
<p class="muted">此页面不会自动刷新；超过一小时或窗口重置后，请重新运行 <code>python3 scripts/codex_usage.py --open</code>。</p>
<p><a href="{USAGE_URL}">官方用量详情</a></p><small>仅保存在本机，请勿分享包含个人额度的页面。</small></section></main></body></html>'''


def write_usage_page(snapshot):
    directory = ROOT / 'workruns' / 'codex-usage-pages'
    for part in (directory, *directory.parents):
        if part.is_symlink():
            raise ValueError('私有页面路径不能包含符号链接。')
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name != 'nt':
        os.chmod(directory, 0o700)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=directory,
                                         prefix='.usage-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(render_html(snapshot))
        target = directory / f'usage-{uuid.uuid4().hex}.html'
        os.replace(temporary, target)
        return target
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
def display(snapshot):
    print('Codex Usage — ' + snapshot['status'])
    print('来源：' + SOURCE)
    print('刷新时间：' + snapshot['fetchedAt'])
    if snapshot.get('message'):
        print(snapshot['message'])
    for bucket in snapshot.get('buckets', []):
        print('\n' + (bucket['name'] or bucket['id']))
        for window in bucket['windows']:
            length = window['durationMins']
            label = f'{length:g} 分钟' if length is not None else '窗口时长未提供'
            used, remaining = window['usedPercent'], window['remainingPercent']
            print(f"  {label}：已用 {f'{used:g}%' if used is not None else '未提供'}，"
                  f"剩余 {f'{remaining:g}%' if remaining is not None else '未提供'}；"
                  f"重置 {display_time(window['resetsAt'])}")
        if bucket.get('credits'):
            print('  额外积分信息：' + json.dumps(bucket['credits'], ensure_ascii=False))
    if snapshot.get('resetCreditsAvailable') is not None:
        print(f"可用额度重置次数：{snapshot['resetCreditsAvailable']}")
    print('详情：' + USAGE_URL + ' 或 Codex CLI /status')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true', help='输出筛选后的 JSON 快照')
    parser.add_argument('--output', help='将本地快照写入 workruns/ 下')
    parser.add_argument('--open', action='store_true', help='查询一次并在浏览器打开本机私有页面')
    parser.add_argument('--timeout', type=float, default=15, help='总超时时间（秒）')
    args = parser.parse_args(argv)
    if not math.isfinite(args.timeout) or not 0 < args.timeout <= 120:
        parser.error('--timeout 必须大于 0 且不超过 120 秒')
    try:
        snapshot = fetch_usage(args.timeout)
    except UsageError as exc:
        snapshot = {'status': exc.status, 'fetchedAt': now(), 'source': SOURCE,
                    'buckets': [], 'resetCreditsAvailable': None, 'message': str(exc)}
    if args.output:
        try:
            write_snapshot(args.output, snapshot)
        except (ValueError, OSError) as exc:
            print(f'无法保存快照：{exc}', file=sys.stderr)
            return 2
    if args.open:
        try:
            page = write_usage_page(snapshot)
            opened = webbrowser.open(page.as_uri(), new=2)
        except (ValueError, OSError, webbrowser.Error) as exc:
            print('无法生成或打开本地额度页面，请检查本机文件和浏览器权限。', file=sys.stderr)
            return 2
        if not opened:
            print('已生成本地额度页面，但浏览器未能打开；请检查默认浏览器设置。', file=sys.stderr)
            return 2
        print('已请求浏览器打开本机私有额度页面。')
    if args.json:
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    elif not args.open:
        display(snapshot)
    return 0 if snapshot['status'] == 'ok' else 1


if __name__ == '__main__':
    raise SystemExit(main())
