"""Scan engine resources through registered adapters without extracting them."""
import argparse
import json
from pathlib import Path
from package import Package
from nsp_runtime.pipeline import scan as scan_pipeline


def scan(package, output, engine='auto'):
    report = scan_pipeline(package, output, engine=engine,
                           progress=lambda event: print(json.dumps(event), flush=True))
    print(json.dumps({k: len(v) if isinstance(v, list) else v for k, v in report.items()}))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package')
    parser.add_argument('keys')
    parser.add_argument('output', type=Path)
    parser.add_argument('--engine', default='auto')
    args = parser.parse_args()
    package = Package(args.package, args.keys)
    try:
        report = scan(package, args.output, args.engine)
    finally:
        package.close()
    raise SystemExit(0 if report['complete'] else 1)
