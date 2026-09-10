#!/usr/bin/env python3
"""Build a single-file executable Python zip application."""

from __future__ import annotations

import argparse
import shutil
import stat
import tempfile
import zipapp
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def build(output: Path) -> Path:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="synadm-tui-build-") as temporary:
        stage = Path(temporary)
        shutil.copytree(ROOT / "synadm_tui", stage / "synadm_tui", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        zipapp.create_archive(
            stage,
            target=output,
            interpreter="/usr/bin/env python3",
            main="synadm_tui.cli:main",
            compressed=True,
        )
    output.chmod(output.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="synadm-tui als einzelne ausführbare Datei bauen")
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "synadm-tui.pyz")
    args = parser.parse_args()
    result = build(args.output)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
