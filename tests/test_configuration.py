import json
import os
import tempfile
import unittest
from pathlib import Path

from synadm_tui.configuration import SynadmConfig, backup_synadm_config, write_synadm_config


class ConfigurationTests(unittest.TestCase):
    def test_writes_complete_owner_only_config_without_exposing_token_in_summary(self) -> None:
        config = SynadmConfig(
            user="@admin:example.org",
            token="super-secret-token",
            protocol="http",
            base_url="https://matrix.example.org",
            homeserver="example.org",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synadm.yaml"
            write_synadm_config(path, config)
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["token"], "super-secret-token")
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
        self.assertNotIn("super-secret-token", config.public_summary())

    def test_rejects_invalid_http_url_and_relative_socket(self) -> None:
        with self.assertRaisesRegex(ValueError, "Basis-URL"):
            SynadmConfig("admin", "token", "http", "matrix.invalid").validate()
        with self.assertRaisesRegex(ValueError, "absoluter Pfad"):
            SynadmConfig("admin", "token", "unix", "synapse.sock").validate()

    def test_backup_is_separate_and_owner_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synadm.yaml"
            path.write_text("original", encoding="utf-8")
            backup = backup_synadm_config(path)
            self.assertEqual(backup.read_text(encoding="utf-8"), "original")
            self.assertEqual(os.stat(backup).st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
