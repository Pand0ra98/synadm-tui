"""Render precomputed RGBA images as portable 256-color half-block cells."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True, slots=True)
class BlockCell:
    character: str
    foreground: int
    background: int


def _asset_path(theme_key: str) -> Path:
    return Path(__file__).resolve().parent / "assets" / f"{theme_key}.block.json"


@lru_cache(maxsize=8)
def load_block_cells(theme_key: str, alpha_threshold: int = 48) -> tuple[tuple[BlockCell | None, ...], ...] | None:
    path = _asset_path(theme_key)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        width, height = int(payload["width"]), int(payload["height"])
        pixels = tuple(str(value) for value in payload["pixels"])
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None
    if width < 1 or height < 2 or height % 2 or len(pixels) != width * height:
        return None

    def color_at(x: int, y: int) -> int | None:
        value = pixels[y * width + x]
        if len(value) != 8:
            return None
        try:
            red, green, blue, alpha = (int(value[index : index + 2], 16) for index in (0, 2, 4, 6))
        except ValueError:
            return None
        return rgb_to_xterm(red, green, blue) if alpha >= alpha_threshold else None

    rows: list[tuple[BlockCell | None, ...]] = []
    for y in range(0, height, 2):
        row: list[BlockCell | None] = []
        for x in range(width):
            top, bottom = color_at(x, y), color_at(x, y + 1)
            if top is None and bottom is None:
                row.append(None)
            elif bottom is None:
                row.append(BlockCell("▀", top if top is not None else 15, -1))
            elif top is None:
                row.append(BlockCell("▄", bottom, -1))
            else:
                row.append(BlockCell("▀", top, bottom))
        rows.append(tuple(row))
    return tuple(rows)


@lru_cache(maxsize=4096)
def rgb_to_xterm(red: int, green: int, blue: int) -> int:
    levels = (0, 95, 135, 175, 215, 255)
    candidates: list[tuple[int, int, int, int]] = []
    for r_index, r_value in enumerate(levels):
        for g_index, g_value in enumerate(levels):
            for b_index, b_value in enumerate(levels):
                candidates.append((16 + 36 * r_index + 6 * g_index + b_index, r_value, g_value, b_value))
    candidates.extend((232 + index, value, value, value) for index, value in enumerate(range(8, 239, 10)))
    return min(
        candidates,
        key=lambda item: (red - item[1]) ** 2 + (green - item[2]) ** 2 + (blue - item[3]) ** 2,
    )[0]
