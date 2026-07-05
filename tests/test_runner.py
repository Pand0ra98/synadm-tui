from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from synadm_tui.runner import SynadmRunner, pretty_output


class RunnerTests(unittest.TestCase):
    def test_build_command_uses_batch_json_and_config(self) -> None:
        runner = SynadmRunner("/usr/bin/synadm", "/tmp/synadm.yaml")
        self.assertEqual(runner.build_command(["user", "list"]), [
            "/usr/bin/synadm", "--batch", "--output", "json",
            "--config-file", "/tmp/synadm.yaml", "user", "list",
        ])

    def test_build_command_does_not_force_json_for_help(self) -> None:
        self.assertEqual(SynadmRunner().build_command(["room", "--help"]), [
            "synadm", "--batch", "room", "--help",
        ])

    def test_pretty_output_formats_json_and_preserves_text(self) -> None:
        self.assertEqual(pretty_output('{"name":"Jörg"}'), '{\n  "name": "Jörg"\n}')
        self.assertEqual(pretty_output("already readable\n"), "already readable")

    @patch("synadm_tui.runner.subprocess.run")
    def test_run_returns_process_result(self, run) -> None:
        run.return_value = subprocess.CompletedProcess([], 0, '{"ok": true}\n', "warning\n")
        result = SynadmRunner(timeout=12).run(["version"])
        self.assertTrue(result.ok)
        self.assertEqual(result.stdout, '{"ok": true}\n')
        self.assertEqual(result.stderr, "warning\n")
        self.assertNotIn("shell", run.call_args.kwargs)
        self.assertIs(run.call_args.kwargs["stdin"], subprocess.DEVNULL)
        self.assertEqual(run.call_args.kwargs["timeout"], 12)

    @patch("synadm_tui.runner.subprocess.run", side_effect=FileNotFoundError)
    def test_missing_executable_is_a_result(self, _run) -> None:
        result = SynadmRunner("not-installed").run(["version"])
        self.assertEqual(result.returncode, 127)
        self.assertIn("nicht gefunden", result.stderr)


if __name__ == "__main__":
    unittest.main()
