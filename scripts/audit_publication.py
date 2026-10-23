#!/usr/bin/env python3
"""Audit a code-only Git tree/index and optionally reachable history, without network access.

This bounded path/content scan is a guardrail, not proof of rights or absence of secrets.
It never prints matched content and does not inspect ignored private inputs.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

LIMIT = 1024 * 1024
MEDIA = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.mp4', '.mov', '.zip', '.pdf', '.psd'}
PATTERNS = {
    'personal_absolute_path': re.compile(r'/(?:Users|home)/[^/\s<>"\']+/'),
    'email_address': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'),
    'private_key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'api_token': re.compile(r'\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{30,})\b'),
}


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args])


def inspect(path, data):
    """Return categories only; never return potentially sensitive matched values."""
    reasons = []
    p = Path(path)
    if (p.parts and p.parts[0] in {'workruns', 'reports', 'private', 'dist', 'build', '.venv'}) or path.startswith('references/private/') or (path.startswith('pets/') and path != 'pets/.gitkeep') or path.startswith('assets/previews/'):
        reasons.append('private_or_artwork_path')
    if p.name == '.env' or (p.name.startswith('.env.') and p.name != '.env.example'):
        reasons.append('environment_file')
    if p.suffix.lower() in MEDIA:
        reasons.append('media_or_archive_in_code_only_tree')
    if len(data) > LIMIT:
        reasons.append('blob_over_1_MiB')
    if (data.startswith((b'\x89PNG\r\n\x1a\n', b'\xff\xd8\xff', b'GIF87a', b'GIF89a',
                         b'%PDF-', b'PK\x03\x04', b'PK\x05\x06', b'OggS'))
            or (data.startswith(b'RIFF') and data[8:12] in (b'WEBP', b'WAVE'))
            or data.lstrip().startswith(b'<svg')):
        reasons.append('media_or_archive_signature')
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        reasons.append('binary_blob')
    else:
        if '\x00' in text:
            reasons.append('binary_blob')
        if text.startswith('version https://git-lfs.github.com/spec/v1'):
            reasons.append('unreviewed_lfs_pointer')
        reasons.extend(name for name, pattern in PATTERNS.items() if pattern.search(text))
    return sorted(set(reasons))


def audit(root, history=False):
    root = Path(root).resolve()
    if Path(git(root, 'rev-parse', '--show-toplevel').decode().strip()).resolve() != root:
        raise ValueError('root must be the Git repository root')
    findings, records = [], []

    def check(scope, path, data):
        reasons = inspect(path, data)
        records.append({'scope': scope, 'path': path, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
        if reasons:
            findings.append({'scope': scope, 'path': path, 'categories': reasons})

    entries = git(root, 'ls-files', '--stage', '-z').split(b'\0')
    for entry in filter(None, entries):
        metadata, raw_path = entry.split(b'\t', 1)
        mode, oid, stage = metadata.decode().split()
        path = raw_path.decode('utf-8')
        if mode not in {'100644', '100755'} or stage != '0':
            findings.append({'scope': 'index', 'path': path, 'categories': ['non_regular_or_unmerged_entry']})
            continue
        check('index', path, git(root, 'cat-file', 'blob', oid))
        target = root / path
        if target.is_symlink():
            findings.append({'scope': 'worktree', 'path': path, 'categories': ['symlink']})
        elif target.is_file():
            check('worktree', path, target.read_bytes())
        else:
            findings.append({'scope': 'worktree', 'path': path, 'categories': ['missing_tracked_file']})
    if history:
        # Enumerate every commit tree: the same blob may have multiple historical paths.
        seen = set()
        for commit in git(root, 'rev-list', '--all').decode().splitlines():
            for entry in filter(None, git(root, 'ls-tree', '-r', '-z', commit).split(b'\0')):
                meta, raw_path = entry.split(b'\t', 1)
                mode, kind, oid = meta.decode().split()
                path = raw_path.decode('utf-8')
                key = (mode, oid, path)
                if key in seen:
                    continue
                seen.add(key)
                if kind != 'blob' or mode not in {'100644', '100755'}:
                    findings.append({'scope': 'history', 'path': path, 'categories': ['non_regular_entry']})
                else:
                    check('history', path, git(root, 'cat-file', 'blob', oid))
    return {'ok': not findings, 'scope': 'tracked worktree and index' + (' plus all reachable commit trees' if history else ''),
            'records': records, 'findings': findings,
            'limits': 'Pattern scan only; commit author identities are not scanned. Ignored files are excluded. No rights, GUI, licensing, or publication approval is granted.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='.')
    parser.add_argument('--history', action='store_true')
    parser.add_argument('--report')
    args = parser.parse_args()
    try:
        result = audit(args.root, args.history)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        result = {'ok': False, 'error': type(exc).__name__}
    if args.report:
        target = Path(args.report)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'records'}, ensure_ascii=False, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
