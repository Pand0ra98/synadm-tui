import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from synadm_tui.audit import append_audit, redact_command


class AuditTests(unittest.TestCase):
    def test_redacts_passwords_and_tokens(self) -> None:
        self.assertEqual(
            redact_command(["synadm", "user", "modify", "@a:x", "--password", "secret", "--token", "abc"]),
            ["synadm", "user", "modify", "@a:x", "--password", "********", "--token", "********"],
        )

    def test_appends_owner_only_json_line(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"XDG_STATE_HOME": directory}):
                path = append_audit(["synadm", "user", "list"], 0, 0.1234)
            record = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(record["command"], ["synadm", "user", "list"])
            self.assertTrue(record["ok"])
            self.assertEqual(stat.S_IMODE(Path(path).stat().st_mode), 0o600)


if __name__ == "__main__":
    unittest.main()
