#!/usr/bin/env python3
"""Build a native one-file executable with PyInstaller."""

from __future__ import annotations

from pathlib import Path

import PyInstaller.__main__


ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    PyInstaller.__main__.run([
        str(ROOT / "scripts" / "standalone_entry.py"),
        "--name=synadm-tui-native",
        "--onefile",
        "--clean",
        f"--paths={ROOT}",
        f"--distpath={ROOT / 'dist'}",
        f"--workpath={ROOT / 'build' / 'pyinstaller'}",
        f"--specpath={ROOT / 'build'}",
    ])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
