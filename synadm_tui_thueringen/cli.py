"""Entry point for the Thüringen edition."""

from __future__ import annotations

from synadm_tui.cli import main as core_main

from .theme import THURINGIA_EDITION, THURINGIA_THEME


def main(argv: list[str] | None = None) -> int:
    return core_main(argv, edition=THURINGIA_EDITION, extra_themes=(THURINGIA_THEME,))
