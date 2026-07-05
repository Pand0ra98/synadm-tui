"""Edition profile used by the shared application core."""

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

EDITIONS = {STANDARD_EDITION.key: STANDARD_EDITION}
