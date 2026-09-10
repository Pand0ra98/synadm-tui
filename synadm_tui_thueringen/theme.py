"""Thüringen profile and visual assets; application behavior comes from synadm-tui."""

from __future__ import annotations

import curses
from pathlib import Path

from synadm_tui.app import Theme
from synadm_tui.edition import Edition

ASSETS = Path(__file__).resolve().parent / "assets"

THURINGIA_CREST = (
    "      .-============-.",
    "     /  *  *  *  *   \\",
    "    |      /\\_/\\      |",
    "    |  ___/ o o \\___   |",
    "    | /   |==^==|   \\  |",
    "    |     /|===|\\      |",
    "     \\  *  *  *  *   /",
    "      '============'",
)

THURINGIA_THEME = Theme(
    "thuringia",
    "Freistaat Thüringen",
    "THÜRINGEN",
    (
        (curses.COLOR_RED, -1),
        (curses.COLOR_WHITE, curses.COLOR_RED),
        (curses.COLOR_CYAN, -1),
        (curses.COLOR_RED, -1),
        (curses.COLOR_YELLOW, -1),
        (curses.COLOR_WHITE, -1),
        (curses.COLOR_BLUE, -1),
        (curses.COLOR_WHITE, curses.COLOR_BLUE),
        (curses.COLOR_RED, curses.COLOR_WHITE),
    ),
    THURINGIA_CREST,
    "FREISTAAT THÜRINGEN // SYSTEM BEREIT",
    image_path=ASSETS / "thueringen-wappen.png",
    block_path=ASSETS / "thuringia.block.json",
)

THURINGIA_EDITION = Edition(
    key="thuringia",
    name="Thüringen Edition",
    binary_name="synadm-tui-thueringen",
    default_theme="thuringia",
    theme_keys=("thuringia", "cyberspace", "matrix", "hacker", "high-contrast", "monochrome"),
)
