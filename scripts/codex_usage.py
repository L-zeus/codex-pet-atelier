#!/usr/bin/env python3
"""Read ChatGPT Codex rate limits once via the local official app-server."""
import argparse
from datetime import datetime, timezone
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
        buckets.append({'id': str(ident)[:128], 'name': name[:128] if isinstance(name, str) else None,
                        'windows': windows, 'credits': safe_credits})
    resets = result.get('rateLimitResetCredits')
    count = resets.get('availableCount') if isinstance(resets, dict) else None
    count = count if isinstance(count, int) and not isinstance(count, bool) and count >= 0 else None
    return {'status': 'ok' if any(b['windows'] for b in buckets) else 'unavailable',
            'fetchedAt': now(), 'source': SOURCE, 'buckets': buckets,
            'resetCreditsAvailable': count,
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
    if args.json:
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    else:
        display(snapshot)
    return 0 if snapshot['status'] == 'ok' else 1


if __name__ == '__main__':
    raise SystemExit(main())
