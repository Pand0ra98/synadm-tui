#!/usr/bin/env python3
"""Publish public RPM keys and repository files to Gitea Generic Packages."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from publish_packages import tea_token, upload

ROOT = Path(__file__).resolve().parent.parent
FILES = (
    "RPM-GPG-KEY-synadm-tui",
    "synadm-tui.repo",
    "synadm-tui-thueringen.repo",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="https://git.blackwall.ipv64.de")
    parser.add_argument("--owner", default="pan")
    parser.add_argument("--username", default="pan")
    parser.add_argument("--registry-version", default="1")
    parser.add_argument("--tea-login", help="Token sicher aus diesem tea-Login lesen")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base = args.base_url.rstrip("/")
    jobs = [
        (
            ROOT / "packaging" / filename,
            (
                f"{base}/api/packages/{args.owner}/generic/"
                f"synadm-tui-repository/{args.registry_version}/{filename}"
            ),
        )
        for filename in FILES
    ]
    missing = [str(path) for path, _url in jobs if not path.is_file()]
    if missing:
        raise SystemExit("Repository-Dateien fehlen: " + ", ".join(missing))
    if args.dry_run:
        for path, url in jobs:
            print(f"{path.name} -> {url}")
        return 0
    token = tea_token(args.tea_login) if args.tea_login else os.environ.get("GITEA_PACKAGE_TOKEN", "")
    if not token:
        raise SystemExit("GITEA_PACKAGE_TOKEN ist nicht gesetzt und --tea-login wurde nicht verwendet.")
    for path, url in jobs:
        print(f"Lade {path.name} hoch …", flush=True)
        upload(path, url, args.username, token)
    print(f"{len(jobs)} Repository-Dateien veröffentlicht.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
