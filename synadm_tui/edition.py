"""Edition profiles; all application behavior remains shared."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Edition:
    key: str
    name: str
    binary_name: str
    default_theme: str
    theme_keys: tuple[str, ...]


STANDARD_EDITION = Edition(
    key="standard",
    name="Standard Edition",
    binary_name="synadm-tui",
    default_theme="cyberspace",
    theme_keys=("cyberspace", "matrix", "hacker", "high-contrast", "monochrome"),
)

THURINGIA_EDITION = Edition(
    key="thuringia",
    name="Thüringen Edition",
    binary_name="synadm-tui-thueringen",
    default_theme="thuringia",
    theme_keys=("thuringia", "cyberspace", "matrix", "hacker", "high-contrast", "monochrome"),
)

EDITIONS = {edition.key: edition for edition in (STANDARD_EDITION, THURINGIA_EDITION)}
