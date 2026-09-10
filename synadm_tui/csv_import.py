"""CSV-Import fuer synadm-tui.

CSV-Datensaetze werden in Argumente fuer
``synadm user modify`` umgewandelt.

Besonderheit:
Die Matrix-Homeserver-Domain wird fuer importierte Benutzer zentral
festgelegt. Dadurch kann die oeffentliche API-Domain von der eigentlichen
Matrix-Domain abweichen.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping


# ---------------------------------------------------------------------------
# Matrix-Konfiguration
# ---------------------------------------------------------------------------

# WICHTIG:
# Dies ist die Domain aus dem Synapse "server_name".
#
# Beispiel:
#   API:        https://matrix.pan-lab.de
#   Matrix-ID:  @benutzer:matrix.djt.lan
#
# Die öffentliche API-Domain darf hier NICHT eingetragen werden.
MATRIX_HOMESERVER = "matrix.djt.lan"


# ---------------------------------------------------------------------------
# CSV-Felder
# ---------------------------------------------------------------------------

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


TRUE_VALUES = {
    "1",
    "ja",
    "j",
    "yes",
    "y",
    "true",
    "wahr",
}

FALSE_VALUES = {
    "0",
    "nein",
    "n",
    "no",
    "false",
    "falsch",
}

DELIMITER_NAMES = {
    "komma": ",",
    "comma": ",",
    "semikolon": ";",
    "semicolon": ";",
    "tab": "\t",
    "tabulator": "\t",
}


# ---------------------------------------------------------------------------
# Datenklassen
# ---------------------------------------------------------------------------

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
    """Fehler beim Einlesen oder Verarbeiten einer CSV-Datei."""


# ---------------------------------------------------------------------------
# CSV einlesen
# ---------------------------------------------------------------------------

def inspect_csv(
    path: str | Path,
    delimiter: str | None = None,
    *,
    has_header: bool = True,
) -> CsvData:
    source = Path(path).expanduser()

    try:
        text = source.read_text(encoding="utf-8-sig")
    except OSError as error:
        raise CsvImportError(
            f"CSV-Datei kann nicht gelesen werden: {error}"
        ) from error

    if not text.strip():
        raise CsvImportError("Die CSV-Datei ist leer.")

    if delimiter:
        actual_delimiter = normalize_delimiter(delimiter)
    else:
        actual_delimiter = detect_delimiter(text)

    try:
        reader = csv.reader(
            io.StringIO(text),
            delimiter=actual_delimiter,
        )

        parsed = [
            tuple(cell.strip() for cell in row)
            for row in reader
        ]

    except csv.Error as error:
        raise CsvImportError(
            f"Ungültige CSV-Datei: {error}"
        ) from error

    # Komplett leere Zeilen entfernen
    parsed = [
        row
        for row in parsed
        if any(cell for cell in row)
    ]

    if not parsed:
        raise CsvImportError(
            "Die CSV-Datei enthält keine Datensätze."
        )

    column_count = max(len(row) for row in parsed)

    if column_count < 1:
        raise CsvImportError(
            "In der CSV-Datei wurden keine Spalten gefunden."
        )

    # Alle Zeilen auf dieselbe Spaltenanzahl bringen
    normalized_rows = [
        row + ("",) * (column_count - len(row))
        for row in parsed
    ]

    if has_header:
        labels = tuple(
            value or f"Spalte {index + 1}"
            for index, value in enumerate(normalized_rows[0])
        )

        rows = normalized_rows[1:]

    else:
        labels = tuple(
            f"Spalte {index + 1}"
            for index in range(column_count)
        )

        rows = normalized_rows

    if not rows:
        raise CsvImportError(
            "Die CSV-Datei enthält nach der Kopfzeile keine Datensätze."
        )

    return CsvData(
        path=source,
        delimiter=actual_delimiter,
        labels=labels,
        rows=tuple(rows),
        first_line_is_header=has_header,
    )


def detect_delimiter(text: str) -> str:
    """Versucht das Trennzeichen automatisch zu erkennen."""

    try:
        dialect = csv.Sniffer().sniff(
            text[:8192],
            delimiters=",;\t|",
        )

        return dialect.delimiter

    except csv.Error:
        # Deutscher CSV-Standardfall
        return ";"


def normalize_delimiter(value: str | None) -> str:
    """Normalisiert ausgeschriebene Trennzeichen."""

    cleaned = (value or "").strip().lower()

    cleaned = DELIMITER_NAMES.get(
        cleaned,
        cleaned,
    )

    if cleaned == r"\t":
        cleaned = "\t"

    if len(cleaned) != 1:
        raise CsvImportError(
            "Das Trennzeichen muss genau ein Zeichen sein."
        )

    return cleaned


# ---------------------------------------------------------------------------
# Matrix-ID
# ---------------------------------------------------------------------------

def normalize_user_id(value: str) -> str:
    """Erzeugt aus einer CSV-Benutzer-ID eine lokale Matrix-ID.

    Beispiele:

        test
        -> @test:matrix.djt.lan

        @test
        -> @test:matrix.djt.lan

        test:matrix.pan-lab.de
        -> @test:matrix.djt.lan

        @test:matrix.pan-lab.de
        -> @test:matrix.djt.lan

        @test:matrix.djt.lan
        -> @test:matrix.djt.lan

    Die in der CSV eventuell vorhandene Domain wird bewusst ignoriert.
    Dadurch werden CSV-Importe immer auf dem lokalen Matrix-Homeserver
    angelegt.
    """

    raw_value = value.strip()

    if not raw_value:
        return ""

    # Führendes @ entfernen
    if raw_value.startswith("@"):
        raw_value = raw_value[1:]

    # Falls bereits eine Domain angegeben wurde:
    #
    #   test:example.org
    #
    # wird nur der Localpart übernommen.
    if ":" in raw_value:
        localpart, _domain = raw_value.split(":", 1)
    else:
        localpart = raw_value

    localpart = localpart.strip()

    if not localpart:
        return ""

    # Leerzeichen sind in Matrix-Localparts ungeeignet und deuten
    # meistens auf eine falsch zugeordnete CSV-Spalte hin.
    if any(character.isspace() for character in localpart):
        raise CsvImportError(
            f"Ungültige Benutzer-ID {value!r}: "
            "Der Benutzername darf keine Leerzeichen enthalten."
        )

    return f"@{localpart}:{MATRIX_HOMESERVER}"


# ---------------------------------------------------------------------------
# Import-Einträge erzeugen
# ---------------------------------------------------------------------------

def build_entries(
    data: CsvData,
    mapping: Mapping[str, int | None],
) -> tuple[ImportEntry, ...]:
    """Erzeugt synadm-Kommandos aus den CSV-Zeilen."""

    user_column = mapping.get("user_id")

    if user_column is None:
        raise CsvImportError(
            "Die Benutzer-ID muss einer Spalte zugeordnet werden."
        )

    entries: list[ImportEntry] = []
    errors: list[str] = []

    first_data_line = (
        2
        if data.first_line_is_header
        else 1
    )

    for row_index, row in enumerate(data.rows):
        line = first_data_line + row_index

        try:
            entry = _build_entry(
                row,
                line,
                mapping,
            )

        except CsvImportError as error:
            errors.append(str(error))

        else:
            entries.append(entry)

    if errors:
        preview = "\n".join(errors[:8])

        suffix = (
            f"\n… und {len(errors) - 8} weitere Fehler"
            if len(errors) > 8
            else ""
        )

        raise CsvImportError(
            preview + suffix
        )

    if not entries:
        raise CsvImportError(
            "Es wurden keine importierbaren Benutzer gefunden."
        )

    return tuple(entries)


def _build_entry(
    row: tuple[str, ...],
    line: int,
    mapping: Mapping[str, int | None],
) -> ImportEntry:
    """Erzeugt einen einzelnen Benutzerimport."""

    values = {
        key: _cell(row, column)
        for key, column in mapping.items()
    }

    raw_user_id = values.get(
        "user_id",
        "",
    ).strip()

    if not raw_user_id:
        raise CsvImportError(
            f"Zeile {line}: Benutzer-ID fehlt."
        )

    try:
        user_id = normalize_user_id(raw_user_id)

    except CsvImportError as error:
        raise CsvImportError(
            f"Zeile {line}: {error}"
        ) from error

    if not user_id:
        raise CsvImportError(
            f"Zeile {line}: Benutzer-ID ist ungültig."
        )

    # Entspricht:
    #
    # synadm user modify @user:matrix.djt.lan ...
    args = [
        "user",
        "modify",
        user_id,
    ]

    _append_value(
        args,
        "--password",
        values.get("password"),
    )

    _append_value(
        args,
        "--display-name",
        values.get("display_name"),
    )

    email = values.get("email", "")

    if email:
        args.extend(
            (
                "--threepid",
                "email",
                email,
            )
        )

    admin = _boolean(
        values.get("admin"),
        line,
        "Administrator",
    )

    if admin is not None:
        args.append(
            "--admin"
            if admin
            else "--no-admin"
        )

    user_type = values.get(
        "user_type",
        "",
    ).strip().lower()

    if user_type:
        allowed_user_types = {
            "regular",
            "bot",
            "support",
        }

        if user_type not in allowed_user_types:
            raise CsvImportError(
                f"Zeile {line}: unbekannter "
                f"Benutzertyp {user_type!r}."
            )

        args.extend(
            (
                "--user-type",
                user_type,
            )
        )

    _append_value(
        args,
        "--avatar-url",
        values.get("avatar_url"),
    )

    locked = _boolean(
        values.get("locked"),
        line,
        "Gesperrt",
    )

    if locked is not None:
        args.append(
            "--lock"
            if locked
            else "--unlock"
        )

    # user modify benötigt neben der ID mindestens eine Änderung.
    if len(args) == 3:
        raise CsvImportError(
            f"Zeile {line}: außer der Benutzer-ID "
            "ist kein Wert zum Anlegen vorhanden."
        )

    return ImportEntry(
        line=line,
        user_id=user_id,
        args=tuple(args),
    )


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _cell(
    row: tuple[str, ...],
    column: int | None,
) -> str:
    """Liest sicher eine einzelne CSV-Zelle."""

    if column is None:
        return ""

    if column < 0:
        return ""

    if column >= len(row):
        return ""

    return row[column].strip()


def _append_value(
    args: list[str],
    option: str,
    value: str | None,
) -> None:
    """Hängt einen Parameter nur bei vorhandenem Wert an."""

    if value:
        args.extend(
            (
                option,
                value,
            )
        )


def _boolean(
    value: str | None,
    line: int,
    title: str,
) -> bool | None:
    """Konvertiert typische ja/nein-Werte."""

    if not value:
        return None

    normalized = value.strip().lower()

    if normalized in TRUE_VALUES:
        return True

    if normalized in FALSE_VALUES:
        return False

    raise CsvImportError(
        f"Zeile {line}: {title} erwartet "
        f"ja/nein, nicht {value!r}."
    )


def redact_args(
    args: Iterable[str],
) -> tuple[str, ...]:
    """Blendet Kennwörter in Logs und Vorschauen aus."""

    redacted: list[str] = []
    hide_next = False

    for part in args:
        if hide_next:
            redacted.append("********")
            hide_next = False
            continue

        redacted.append(part)

        if part in {
            "--password",
            "-P",
        }:
            hide_next = True

    return tuple(redacted)
