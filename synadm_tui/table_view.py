"""Filterable and sortable rendering for structured synadm JSON results."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

PREFERRED_COLLECTIONS = (
    "users", "rooms", "media", "devices", "members", "joined_rooms", "chunk", "results",
)


def _find_rows(value: object, label: str = "value") -> list[dict[str, Any]] | None:
    if isinstance(value, list) and value:
        if all(isinstance(item, dict) for item in value):
            return [dict(item) for item in value]
        if all(not isinstance(item, (dict, list)) for item in value):
            return [{label: item} for item in value]
    if isinstance(value, dict):
        for key in PREFERRED_COLLECTIONS:
            if key in value:
                found = _find_rows(value[key], key)
                if found:
                    return found
        for key in ("action", "verification", "data", "result"):
            if key not in value:
                continue
            found = _find_rows(value[key], key)
            if found:
                return found
    return None


def _display(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "ja" if value else "nein"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value).replace("\n", " ")


@dataclass(slots=True)
class TableView:
    rows: list[dict[str, Any]]
    filter_text: str = ""
    sort_key: str = ""
    descending: bool = False
    selected: int = 0
    columns: list[str] = field(init=False)

    def __post_init__(self) -> None:
        self.columns = []
        for row in self.rows:
            for key in row:
                if key not in self.columns:
                    self.columns.append(key)
        if self.columns:
            self.sort_key = self.sort_key or self.columns[0]

    @classmethod
    def from_json(cls, text: str) -> TableView | None:
        try:
            payload = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            payloads: list[object] = []
            decoder = json.JSONDecoder()
            position = 0
            while position < len(text):
                starts = [index for token in ("{", "[") if (index := text.find(token, position)) >= 0]
                if not starts:
                    break
                start = min(starts)
                try:
                    value, end = decoder.raw_decode(text, start)
                except json.JSONDecodeError:
                    position = start + 1
                    continue
                payloads.append(value)
                position = end
            merged: list[dict[str, Any]] = []
            for value in payloads:
                found = _find_rows(value)
                if found:
                    merged.extend(found)
            return cls(merged) if merged else None
        rows = _find_rows(payload)
        if not rows:
            return None
        return cls(rows)

    def visible_rows(self) -> list[dict[str, Any]]:
        needle = self.filter_text.casefold().strip()
        rows = self.rows
        if needle:
            rows = [
                row for row in rows
                if needle in " ".join(_display(value) for value in row.values()).casefold()
            ]
        if self.sort_key:
            rows = sorted(
                rows,
                key=lambda row: _display(row.get(self.sort_key)).casefold(),
                reverse=self.descending,
            )
        return rows

    def select_sort(self, key: str) -> None:
        if key == self.sort_key:
            self.descending = not self.descending
        else:
            self.sort_key = key
            self.descending = False
        self.selected = 0

    def move(self, delta: int) -> None:
        rows = self.visible_rows()
        if not rows:
            self.selected = 0
            return
        self.selected = max(0, min(self.selected + delta, len(rows) - 1))

    def selected_row(self) -> dict[str, Any] | None:
        rows = self.visible_rows()
        if not rows:
            return None
        self.selected = max(0, min(self.selected, len(rows) - 1))
        return rows[self.selected]

    def selected_user_id(self) -> str | None:
        row = self.selected_row()
        if row is None:
            return None
        for key in ("name", "user_id", "userId", "mxid"):
            value = row.get(key)
            if isinstance(value, str) and value.startswith("@") and ":" in value:
                return value
        return None

    def render(self, width: int) -> list[str]:
        width = max(8, width)
        visible = self.visible_rows()
        direction = "↓" if self.descending else "↑"
        filter_info = f" · Filter: {self.filter_text}" if self.filter_text else ""
        meta = f"Tabelle {len(visible)}/{len(self.rows)} · Sortierung: {self.sort_key} {direction}{filter_info}"
        if not self.columns:
            return [meta[:width], "(keine Spalten)"]
        column_count = max(1, min(len(self.columns), 8, width // 12))
        columns = self.columns[:column_count]
        separator_width = 3 * (column_count - 1)
        available = max(column_count * 4, width - separator_width - 2)
        base = max(4, available // column_count)
        widths = [base] * column_count
        widths[-1] += max(0, available - sum(widths))

        def row_line(values: list[str], marker: str = "  ") -> str:
            cells = []
            for value, cell_width in zip(values, widths):
                shortened = value if len(value) <= cell_width else value[: max(1, cell_width - 1)] + "…"
                cells.append(f"{shortened:<{cell_width}}")
            return (marker + " │ ".join(cells))[:width]

        lines = [meta[:width], row_line([column.upper() for column in columns])]
        lines.append("─" * min(width, len(lines[-1])))
        for index, row in enumerate(visible):
            marker = "▶ " if index == self.selected else "  "
            lines.append(row_line([_display(row.get(column)) for column in columns], marker))
        return lines
