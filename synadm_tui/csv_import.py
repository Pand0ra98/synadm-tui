"""CSV parsing and conversion into ``synadm user modify`` commands."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping


@dataclass(frozen=True, slots=True)
class Field:
    key: str
    title: str
    required: bool = False


FIELDS = (
    Field("user_id", "Benutzer-ID", True),
    Field("password", "Passwort"),
    Field("display_name", "Anzeigename"),
    Field("email", "E-Mail"),
    Field("admin", "Administrator (ja/nein)"),
    Field("user_type", "Benutzertyp (regular/bot/support)"),
    Field("avatar_url", "Avatar-URL (mxc://… )"),
    Field("locked", "Gesperrt (ja/nein)"),
)

TRUE_VALUES = {"1", "ja", "j", "yes", "y", "true", "wahr"}
FALSE_VALUES = {"0", "nein", "n", "no", "false", "falsch"}
DELIMITER_NAMES = {"komma": ",", "comma": ",", "semikolon": ";", "semicolon": ";", "tab": "\t", "tabulator": "\t"}


@dataclass(frozen=True, slots=True)
class CsvData:
    path: Path
    delimiter: str
    labels: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    first_line_is_header: bool


@dataclass(frozen=True, slots=True)
class ImportEntry:
    line: int
    user_id: str
    args: tuple[str, ...]


class CsvImportError(ValueError):
    pass


def inspect_csv(path: str | Path, delimiter: str | None = None, *, has_header: bool = True) -> CsvData:
    source = Path(path).expanduser()
    try:
        text = source.read_text(encoding="utf-8-sig")
    except OSError as error:
        raise CsvImportError(f"CSV-Datei kann nicht gelesen werden: {error}") from error
    if not text.strip():
        raise CsvImportError("Die CSV-Datei ist leer.")

    actual_delimiter = normalize_delimiter(delimiter) if delimiter else detect_delimiter(text)
    try:
        parsed = [tuple(cell.strip() for cell in row) for row in csv.reader(io.StringIO(text), delimiter=actual_delimiter)]
    except csv.Error as error:
        raise CsvImportError(f"Ungültige CSV-Datei: {error}") from error
    parsed = [row for row in parsed if any(row)]
    if not parsed:
        raise CsvImportError("Die CSV-Datei enthält keine Datensätze.")
    column_count = max(len(row) for row in parsed)
    if column_count < 1:
        raise CsvImportError("In der CSV-Datei wurden keine Spalten gefunden.")
    normalized = [row + ("",) * (column_count - len(row)) for row in parsed]
    if has_header:
        labels = tuple(value or f"Spalte {index + 1}" for index, value in enumerate(normalized[0]))
        rows = normalized[1:]
    else:
        labels = tuple(f"Spalte {index + 1}" for index in range(column_count))
        rows = normalized
    if not rows:
        raise CsvImportError("Die CSV-Datei enthält nach der Kopfzeile keine Datensätze.")
    return CsvData(source, actual_delimiter, labels, tuple(rows), has_header)


def detect_delimiter(text: str) -> str:
    try:
        return csv.Sniffer().sniff(text[:8192], delimiters=",;\t|").delimiter
    except csv.Error:
        return ";"


def normalize_delimiter(value: str | None) -> str:
    cleaned = (value or "").strip().lower()
    cleaned = DELIMITER_NAMES.get(cleaned, cleaned)
    if cleaned == r"\t":
        cleaned = "\t"
    if len(cleaned) != 1:
        raise CsvImportError("Das Trennzeichen muss genau ein Zeichen sein.")
    return cleaned


def build_entries(data: CsvData, mapping: Mapping[str, int | None]) -> tuple[ImportEntry, ...]:
    user_column = mapping.get("user_id")
    if user_column is None:
        raise CsvImportError("Die Benutzer-ID muss einer Spalte zugeordnet werden.")
    entries: list[ImportEntry] = []
    errors: list[str] = []
    first_data_line = 2 if data.first_line_is_header else 1
    for row_index, row in enumerate(data.rows):
        line = first_data_line + row_index
        try:
            entry = _build_entry(row, line, mapping)
        except CsvImportError as error:
            errors.append(str(error))
        else:
            entries.append(entry)
    if errors:
        preview = "\n".join(errors[:8])
        suffix = f"\n… und {len(errors) - 8} weitere Fehler" if len(errors) > 8 else ""
        raise CsvImportError(preview + suffix)
    if not entries:
        raise CsvImportError("Es wurden keine importierbaren Benutzer gefunden.")
    return tuple(entries)


def _build_entry(row: tuple[str, ...], line: int, mapping: Mapping[str, int | None]) -> ImportEntry:
    values = {key: _cell(row, column) for key, column in mapping.items()}
    user_id = values.get("user_id", "").strip()
    if not user_id:
        raise CsvImportError(f"Zeile {line}: Benutzer-ID fehlt.")
    args = ["user", "modify", user_id]
    _append_value(args, "--password", values.get("password"))
    _append_value(args, "--display-name", values.get("display_name"))
    if values.get("email"):
        args += ["--threepid", "email", values["email"]]
    admin = _boolean(values.get("admin"), line, "Administrator")
    if admin is not None:
        args.append("--admin" if admin else "--no-admin")
    user_type = values.get("user_type", "").lower()
    if user_type:
        if user_type not in {"regular", "bot", "support"}:
            raise CsvImportError(f"Zeile {line}: unbekannter Benutzertyp {user_type!r}.")
        args += ["--user-type", user_type]
    _append_value(args, "--avatar-url", values.get("avatar_url"))
    locked = _boolean(values.get("locked"), line, "Gesperrt")
    if locked is not None:
        args.append("--lock" if locked else "--unlock")
    if len(args) == 3:
        raise CsvImportError(f"Zeile {line}: außer der Benutzer-ID ist kein Wert zum Anlegen vorhanden.")
    return ImportEntry(line, user_id, tuple(args))


def _cell(row: tuple[str, ...], column: int | None) -> str:
    if column is None or column < 0 or column >= len(row):
        return ""
    return row[column].strip()


def _append_value(args: list[str], option: str, value: str | None) -> None:
    if value:
        args.extend((option, value))


def _boolean(value: str | None, line: int, title: str) -> bool | None:
    if not value:
        return None
    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise CsvImportError(f"Zeile {line}: {title} erwartet ja/nein, nicht {value!r}.")


def redact_args(args: Iterable[str]) -> tuple[str, ...]:
    """Hide password values for logs and previews."""
    redacted: list[str] = []
    hide_next = False
    for part in args:
        if hide_next:
            redacted.append("********")
            hide_next = False
        else:
            redacted.append(part)
            hide_next = part in {"--password", "-P"}
    return tuple(redacted)
