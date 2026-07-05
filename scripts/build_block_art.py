#!/usr/bin/env python3
"""Precompute tiny RGBA grids for protocol-free terminal image rendering."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "synadm_tui" / "assets"
SOURCES = {
    "thuringia": "thueringen-wappen.png",
    "cyberspace": "retro-cyberspace.png",
    "hacker": "hacker-terminal.png",
}
PIXEL = re.compile(r"#([0-9A-Fa-f]{8})\s")


def build(theme: str, filename: str) -> Path:
    process = subprocess.run(
        ["convert", str(ASSETS / filename), "-filter", "Lanczos", "-resize", "18x20!", "txt:-"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    pixels = [match.group(1).lower() for line in process.stdout.splitlines() if (match := PIXEL.search(line))]
    if len(pixels) != 18 * 20:
        raise RuntimeError(f"Expected 360 pixels for {theme}, got {len(pixels)}")
    target = ASSETS / f"{theme}.block.json"
    target.write_text(
        json.dumps({"width": 18, "height": 20, "pixels": pixels}, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return target


def main() -> int:
    for theme, filename in SOURCES.items():
        print(build(theme, filename))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
