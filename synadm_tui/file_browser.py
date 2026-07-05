"""Filesystem helpers for the CSV file picker."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class BrowserEntry:
    path: Path
    is_dir: bool

    @property
    def label(self) -> str:
        return f"[Ordner] {self.path.name}/" if self.is_dir else f"         {self.path.name}"


def list_entries(directory: str | Path, *, csv_only: bool = True) -> tuple[BrowserEntry, ...]:
    root = Path(directory).expanduser()
    entries: list[BrowserEntry] = []
    try:
        children = root.iterdir()
        for child in children:
            try:
                is_dir = child.is_dir()
                is_file = child.is_file()
            except OSError:
                continue
            if is_dir or (is_file and (not csv_only or child.suffix.lower() == ".csv")):
                entries.append(BrowserEntry(child, is_dir))
    except OSError as error:
        raise ValueError(f"Verzeichnis kann nicht gelesen werden: {error}") from error
    entries.sort(key=lambda entry: (not entry.is_dir, entry.path.name.casefold()))
    return tuple(entries)
