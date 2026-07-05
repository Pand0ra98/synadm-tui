import curses
import unittest
from unittest.mock import patch

from synadm_tui.app import App
from synadm_tui.runner import Result, SynadmRunner


class NavigationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = App(SynadmRunner("missing-for-test"))

    def test_starts_in_sections_and_enters_commands(self) -> None:
        self.assertEqual(self.app.focus, "sections")
        self.app._handle_key(None, curses.KEY_DOWN)  # type: ignore[arg-type]
        self.assertEqual(self.app.selection.section, 1)
        self.assertEqual(self.app.selection.command, 0)
        self.app._handle_key(None, 10)  # type: ignore[arg-type]
        self.assertEqual(self.app.focus, "commands")
        self.app._handle_key(None, curses.KEY_DOWN)  # type: ignore[arg-type]
        self.assertEqual(self.app.selection.command, 1)

    def test_left_returns_to_sections(self) -> None:
        self.app.focus = "commands"
        self.app._handle_key(None, curses.KEY_LEFT)  # type: ignore[arg-type]
        self.assertEqual(self.app.focus, "sections")

    def test_section_selection_wraps(self) -> None:
        self.app._handle_key(None, curses.KEY_UP)  # type: ignore[arg-type]
        self.assertEqual(self.app.selection.section, 5)

    def test_server_check_updates_state_and_version(self) -> None:
        self.app.server_events.put(Result(("synadm", "version"), 0, '{"server_version":"1.99.0"}', "", 0.1))
        self.app._collect_server_status()
        self.assertEqual(self.app.server_state, "Verbunden")
        self.assertEqual(self.app.server_version, "1.99.0")

    def test_completed_command_is_added_to_activity(self) -> None:
        self.app.pending_activity = "user list"
        self.app.events.put(Result(("synadm", "user", "list"), 0, "[]", "", 0.1))
        self.app._collect_result()
        self.assertEqual(self.app.activities[0].label, "user list")
        self.assertTrue(self.app.activities[0].ok)

    @patch("synadm_tui.app.App._confirm_package_action", return_value=False)
    @patch("synadm_tui.app.shutil.which")
    def test_installer_offers_to_install_missing_pipx(self, which, confirm) -> None:
        which.side_effect = lambda name: None if name == "pipx" else "/usr/bin/python3"
        self.app._install_synadm(None)  # type: ignore[arg-type]
        self.assertEqual(self.app.status, "Installation abgebrochen")
        self.assertIn("pipx fehlt", confirm.call_args.args[1])

    @patch("synadm_tui.app.shutil.which", return_value="/usr/bin/pipx")
    @patch("synadm_tui.app.App._pipx_managed_apps", return_value={"synadm", "other-tool"})
    def test_pipx_removal_refuses_when_other_apps_exist(self, _apps, _which) -> None:
        self.app._uninstall_pipx(None)  # type: ignore[arg-type]
        self.assertIn("weitere Anwendungen", self.app.status)
        self.assertIn("other-tool", self.app.output)

    @patch("synadm_tui.app.shutil.which", return_value="/usr/bin/apt-get")
    @patch("synadm_tui.app.os.geteuid", return_value=0)
    def test_system_pipx_uses_detected_package_manager(self, _euid, _which) -> None:
        self.assertEqual(
            self.app._pipx_remove_command("/usr/bin/pipx"),
            ["apt-get", "remove", "-y", "pipx"],
        )


if __name__ == "__main__":
    unittest.main()
