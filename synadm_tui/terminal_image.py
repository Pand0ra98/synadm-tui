"""Optional inline PNG rendering for terminals implementing Kitty graphics."""

from __future__ import annotations

import base64
import os
from collections.abc import Mapping
from pathlib import Path

IMAGE_ID = 73113


THEME_IMAGES = {
    "cyberspace": "retro-cyberspace.png",
    "hacker": "hacker-terminal.png",
}


def theme_image_path(theme_key: str) -> Path | None:
    filename = THEME_IMAGES.get(theme_key)
    if filename is None:
        return None
    return Path(__file__).resolve().parent / "assets" / filename


def supports_kitty_graphics(environment: Mapping[str, str] | None = None) -> bool:
    env = os.environ if environment is None else environment
    term = env.get("TERM", "").casefold()
    term_program = env.get("TERM_PROGRAM", "").casefold()
    return bool(env.get("KITTY_WINDOW_ID")) or "kitty" in term or term_program in {"wezterm", "ghostty"}


def kitty_render_sequence(data: bytes, row: int, column: int, rows: int, columns: int) -> bytes:
    encoded = base64.b64encode(data)
    chunks = [encoded[index : index + 4096] for index in range(0, len(encoded), 4096)] or [b""]
    result = [b"\x1b7", f"\x1b[{row};{column}H".encode("ascii")]
    for index, chunk in enumerate(chunks):
        more = 1 if index < len(chunks) - 1 else 0
        if index == 0:
            control = f"a=T,f=100,t=d,q=2,C=1,i={IMAGE_ID},p=1,c={columns},r={rows},z=1,m={more}"
        else:
            control = f"q=2,i={IMAGE_ID},m={more}"
        result.extend((b"\x1b_G", control.encode("ascii"), b";", chunk, b"\x1b\\"))
    result.append(b"\x1b8")
    return b"".join(result)


def kitty_delete_sequence() -> bytes:
    return f"\x1b_Ga=d,d=I,q=2,i={IMAGE_ID};\x1b\\".encode("ascii")


def write_terminal_sequence(sequence: bytes) -> None:
    offset = 0
    while offset < len(sequence):
        offset += os.write(1, sequence[offset:])
