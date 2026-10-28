#!/usr/bin/env python3
"""Create a local preview page pointing at existing pet packages, without changing them."""
import argparse
import json
import os
from pathlib import Path
import sys
from urllib.parse import quote

from petlib import reject_symlink_chain, validate

ROOT = Path(__file__).resolve().parents[1]


def relative_url(target, directory):
    return quote(Path(os.path.relpath(target, directory)).as_posix(), safe='/')


def build(packages, output):
    if len(packages) != 3:
        raise ValueError('请按蓝鲸、橙花、银龙的顺序提供三个角色包。')
    output = Path(output).absolute()
    reject_symlink_chain(output)
    output = output.resolve()
    allowed = (ROOT / 'workruns').resolve()
    if allowed not in output.parents:
        raise ValueError('预览页只能生成在 workruns/ 下。')
    if output.exists():
        raise ValueError('输出文件已存在，拒绝覆盖；请指定新路径。')
    sprites = []
    for package in packages:
        package = Path(package).absolute()
        report = validate(package)
        if not report['ok']:
            raise ValueError('角色包校验失败：' + '; '.join(report['errors']))
        sprites.append({'src': relative_url(package / 'spritesheet.webp', output.parent)})
    template = (ROOT / 'preview/index.html').read_text(encoding='utf-8')
    template = template.replace('href="style.css"', f'href="{relative_url(ROOT / "preview/style.css", output.parent)}"')
    template = template.replace('src="app.js"', f'src="{relative_url(ROOT / "preview/app.js", output.parent)}"')
    template = template.replace('href="../README.md"', f'href="{relative_url(ROOT / "README.md", output.parent)}"')
    config = json.dumps(sprites, ensure_ascii=False).replace('<', '\\u003c')
    template = template.replace('<!-- PET_ATLAS_CONFIG -->', f'<script type="application/json" id="initial-pets">{config}</script>')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as target:
        target.write(template)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('packages', nargs=3, metavar='PET', help='按蓝鲸、橙花、银龙顺序提供角色包目录')
    parser.add_argument('--output', default='workruns/v1_8-preview/index.html')
    args = parser.parse_args()
    try:
        result = build(args.packages, args.output)
    except (ValueError, OSError) as exc:
        print(f'无法生成预览：{exc}', file=sys.stderr)
        return 1
    print(f'已生成本地预览：{result}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
