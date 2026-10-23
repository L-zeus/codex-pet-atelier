#!/usr/bin/env python3
"""Validate a local Codex v1 pet package; exit 1 on any machine error."""
import argparse
import json
from petlib import reject_package_output, validate, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package')
    parser.add_argument('--report')
    args = parser.parse_args()
    if args.report:
        try:
            reject_package_output(args.package, args.report)
        except (ValueError, OSError) as exc:
            parser.exit(1, f'{exc}\n')
    result = validate(args.package)
    if args.report:
        write_json(args.report, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
