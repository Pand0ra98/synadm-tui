#!/usr/bin/env python3
"""Upload locally built DEB and RPM files to the Gitea Package Registry."""

from __future__ import annotations

import argparse
import base64
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIR = ROOT / "dist" / "packages"
DEFAULT_DISTRIBUTION = "stable"
DEFAULT_RPM_GROUP = ""


def project_version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


def package_files(version: str) -> tuple[list[Path], list[Path]]:
    debs = sorted(PACKAGE_DIR.glob(f"*_{version}_*.deb"))
    rpms = sorted(PACKAGE_DIR.glob(f"*-{version}-*.rpm"))
    return debs, rpms


def tea_token(login_name: str) -> str:
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    config = config_home / "tea" / "config.yml"
    if not config.is_file():
        raise SystemExit(f"tea-Konfiguration fehlt: {config}")
    selected = False
    for raw_line in config.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("- name:"):
            name = stripped.split(":", 1)[1].strip().strip("\"'")
            selected = name == login_name
            continue
        if selected and stripped.startswith("token:"):
            token = stripped.split(":", 1)[1].strip().strip("\"'")
            if token:
                return token
    raise SystemExit(f"tea-Login nicht gefunden oder ohne Token: {login_name}")


def upload(path: Path, url: str, username: str, token: str) -> None:
    credentials = base64.b64encode(f"{username}:{token}".encode()).decode()
    request = urllib.request.Request(
        url,
        data=path.read_bytes(),
        method="PUT",
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/octet-stream",
            "Content-Length": str(path.stat().st_size),
            "User-Agent": "synadm-tui-package-publisher",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            if response.status not in (200, 201, 204):
                raise RuntimeError(f"unerwarteter HTTP-Status {response.status}")
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Upload von {path.name} fehlgeschlagen: HTTP {error.code}: {detail}") from error


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="https://git.blackwall.ipv64.de")
    parser.add_argument("--owner", default="pan")
    parser.add_argument("--username", default="pan")
    parser.add_argument("--distribution", default=DEFAULT_DISTRIBUTION)
    parser.add_argument("--component", default="main")
    parser.add_argument("--rpm-group", default=DEFAULT_RPM_GROUP)
    parser.add_argument("--tea-login", help="Token sicher aus diesem tea-Login lesen")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    version = project_version()
    debs, rpms = package_files(version)
    if not debs or not rpms:
        raise SystemExit("DEB- oder RPM-Dateien fehlen; zuerst scripts/build_packages.py ausführen.")
    base = args.base_url.rstrip("/")
    deb_url = (
        f"{base}/api/packages/{args.owner}/debian/pool/"
        f"{args.distribution}/{args.component}/upload"
    )
    rpm_group = f"/{args.rpm_group.strip('/')}" if args.rpm_group else ""
    rpm_url = f"{base}/api/packages/{args.owner}/rpm{rpm_group}/upload"
    jobs = [(path, deb_url) for path in debs] + [(path, rpm_url) for path in rpms]
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
    print(f"{len(jobs)} Pakete veröffentlicht.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
