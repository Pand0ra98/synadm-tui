from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from synadm_tui.fake_synadm import FakeSynadmRunner, execute


class FakeSynadmTests(unittest.TestCase):
    def test_runner_creates_lists_searches_and_deactivates_users(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "demo.json"
            runner = FakeSynadmRunner(state)

            created = runner.run([
                "user", "modify", "@alice:demo.local",
                "--password", "Start-123",
                "--display-name", "Alice Demo",
                "--threepid", "email", "alice@example.org",
                "--admin",
            ])
            self.assertTrue(created.ok, created.stderr)
            payload = json.loads(created.stdout)
            self.assertEqual(payload["user"]["name"], "@alice:demo.local")
            self.assertTrue(payload["user"]["admin"])

            listed = runner.run(["user", "list"])
            self.assertTrue(listed.ok, listed.stderr)
            self.assertEqual(json.loads(listed.stdout)["users"][0]["name"], "@alice:demo.local")

            searched = runner.run(["user", "search", "alice"])
            self.assertEqual(json.loads(searched.stdout)["users"][0]["displayname"], "Alice Demo")

            deleted = runner.run(["user", "deactivate", "--gdpr-erase", "@alice:demo.local"])
            self.assertTrue(deleted.ok, deleted.stderr)
            self.assertTrue(json.loads(deleted.stdout)["user"]["deactivated"])
            self.assertTrue(json.loads(deleted.stdout)["gdpr_erase"])

    def test_demo_backend_creates_rooms_from_matrix_raw_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "demo.json"
            payload = {
                "name": "Projekt Alpha",
                "room_alias_name": "projekt-alpha",
                "topic": "Demo",
                "visibility": "private",
                "invite": ["@alice:demo.local"],
            }
            response = execute([
                "matrix", "raw", "client/v3/createRoom",
                "--method", "post",
                "--data", json.dumps(payload),
            ], state)

            self.assertEqual(response.returncode, 0, response.stderr)
            room = json.loads(response.stdout)["room"]
            self.assertEqual(room["name"], "Projekt Alpha")
            self.assertEqual(room["canonical_alias"], "#projekt-alpha:demo.local")
            self.assertEqual(room["members"], ["@alice:demo.local"])

            rooms = execute(["room", "list"], state)
            self.assertEqual(json.loads(rooms.stdout)["rooms"][0]["room_id"], room["room_id"])

    def test_module_cli_accepts_synadm_global_options(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "demo.json"
            completed = subprocess.run(
                [
                    sys.executable, "-m", "synadm_tui.fake_synadm",
                    "--batch", "--output", "json",
                    "user", "modify", "@bob:demo.local", "--display-name", "Bob",
                ],
                check=False,
                capture_output=True,
                text=True,
                env={"SYNADM_TUI_DEMO_STATE": str(state)},
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(completed.stdout)["user"]["displayname"], "Bob")


if __name__ == "__main__":
    unittest.main()
