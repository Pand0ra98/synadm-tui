#!/usr/bin/env python3
"""Build a native one-file executable with PyInstaller."""

from __future__ import annotations

import hashlib
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    builds = (
        ("standalone_entry.py", "synadm-tui", ()),
        (
            "standalone_thueringen_entry.py",
            "synadm-tui-thueringen",
            ("thueringen-wappen.png", "thuringia.block.json"),
        ),
    )
    for entry, name, edition_assets in builds:
        arguments = [
            str(ROOT / "scripts" / entry),
            f"--name={name}",
            "--onefile",
            "--clean",
            f"--paths={ROOT}",
            f"--distpath={ROOT / 'dist'}",
            f"--workpath={ROOT / 'build' / 'pyinstaller' / name}",
            f"--specpath={ROOT / 'build'}",
        ]
        assets = [
            "retro-cyberspace.png", "hacker-terminal.png",
            "cyberspace.block.json", "hacker.block.json",
        ]
        for asset in assets:
            arguments.append(
                f"--add-data={ROOT / 'synadm_tui' / 'assets' / asset}:synadm_tui/assets"
            )
        for asset in edition_assets:
            arguments.append(
                f"--add-data={ROOT / 'synadm_tui_thueringen' / 'assets' / asset}:synadm_tui_thueringen/assets"
            )
        PyInstaller.__main__.run(arguments)
    checksum_lines = []
    for _entry, name, _edition_assets in builds:
        artifact = ROOT / "dist" / name
        checksum = hashlib.sha256(artifact.read_bytes()).hexdigest()
        checksum_lines.append(f"{checksum}  {name}")
    (ROOT / "dist" / "SHA256SUMS").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
