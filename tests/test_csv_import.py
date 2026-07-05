from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from synadm_tui.csv_import import (
    CsvImportError,
    build_entries,
    inspect_csv,
    normalize_delimiter,
    redact_args,
)


class CsvImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.directory.cleanup()

    def csv(self, text: str) -> Path:
        path = Path(self.directory.name) / "users.csv"
        path.write_text(text, encoding="utf-8")
        return path

    def test_detects_semicolon_and_builds_synadm_arguments(self) -> None:
        data = inspect_csv(self.csv(
            "username;passwort;name;email;admin;typ;gesperrt\n"
            "@alice:example.org;secret;Alice;alice@example.org;ja;regular;nein\n"
        ))
        self.assertEqual(data.delimiter, ";")
        entries = build_entries(data, {
            "user_id": 0,
            "password": 1,
            "display_name": 2,
            "email": 3,
            "admin": 4,
            "user_type": 5,
            "avatar_url": None,
            "locked": 6,
        })
        self.assertEqual(entries[0].line, 2)
        self.assertEqual(entries[0].args, (
            "user", "modify", "@alice:example.org",
            "--password", "secret",
            "--display-name", "Alice",
            "--threepid", "email", "alice@example.org",
            "--admin", "--user-type", "regular", "--unlock",
        ))

    def test_supports_csv_without_header(self) -> None:
        data = inspect_csv(self.csv("bob,Temp123,Bob\n"), ",", has_header=False)
        self.assertEqual(data.labels, ("Spalte 1", "Spalte 2", "Spalte 3"))
        entry = build_entries(data, {"user_id": 0, "password": 1, "display_name": 2})[0]
        self.assertEqual(entry.line, 1)
        self.assertEqual(entry.user_id, "bob")

    def test_rejects_invalid_boolean_with_source_line(self) -> None:
        data = inspect_csv(self.csv("user;admin\nalice;vielleicht\n"))
        with self.assertRaisesRegex(CsvImportError, "Zeile 2.*ja/nein"):
            build_entries(data, {"user_id": 0, "admin": 1})

    def test_requires_value_besides_user_id(self) -> None:
        data = inspect_csv(self.csv("user\nalice\n"), ";")
        with self.assertRaisesRegex(CsvImportError, "kein Wert"):
            build_entries(data, {"user_id": 0})

    def test_delimiter_names_and_password_redaction(self) -> None:
        self.assertEqual(normalize_delimiter("tab"), "\t")
        self.assertEqual(normalize_delimiter("Semikolon"), ";")
        self.assertEqual(
            redact_args(("user", "modify", "alice", "--password", "secret")),
            ("user", "modify", "alice", "--password", "********"),
        )


if __name__ == "__main__":
    unittest.main()
