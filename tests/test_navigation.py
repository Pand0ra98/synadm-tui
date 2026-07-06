import curses
import json
import unittest
from unittest.mock import ANY, Mock, patch

from synadm_tui.app import App, WIZARD_BACK
from synadm_tui.catalog import SECTIONS
from synadm_tui.runner import Result, SynadmRunner
from synadm_tui.table_view import TableView


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

    def test_server_panel_grows_and_keeps_layout_consistent(self) -> None:
        layout = self.app._panel_layout(40, 140)
        assert layout is not None
        self.assertGreaterEqual(layout.left_width, 34)
        self.assertEqual(layout.server_height, 10)
        self.assertEqual(layout.sections_y, layout.body_y + layout.server_height)
        self.assertEqual(
            layout.quick_height,
            layout.body_height - layout.server_height - layout.sections_height,
        )

    def test_server_panel_text_wraps_with_aligned_continuation(self) -> None:
        lines = self.app._wrap_panel_value(
            "Status",
            "Konfiguration gespeichert und Verbindungstest fehlgeschlagen",
            24,
        )
        self.assertGreater(len(lines), 1)
        self.assertTrue(lines[0].startswith("Status: "))
        self.assertTrue(lines[1].startswith("        "))
        self.assertTrue(all(len(line) <= 24 for line in lines))

    def test_left_returns_to_sections(self) -> None:
        self.app.focus = "commands"
        self.app._handle_key(None, curses.KEY_LEFT)  # type: ignore[arg-type]
        self.assertEqual(self.app.focus, "sections")

    @patch("synadm_tui.app.App._prepare_command")
    @patch("synadm_tui.app.curses.getmouse")
    def test_mouse_selects_users_and_opens_user_search(self, getmouse, prepare) -> None:
        screen = Mock()
        screen.getmaxyx.return_value = (40, 140)
        layout = self.app._panel_layout(40, 140)
        assert layout is not None
        users_index = next(index for index, section in enumerate(SECTIONS) if section.title == "Benutzer")
        getmouse.return_value = (
            0,
            3,
            layout.sections_y + 1 + users_index,
            0,
            curses.BUTTON1_CLICKED,
        )
        self.app._handle_key(screen, curses.KEY_MOUSE)
        self.assertEqual(self.app.selection.section, users_index)
        self.assertEqual(self.app.focus, "commands")
        prepare.assert_not_called()

        search_index = next(
            index
            for index, command in enumerate(SECTIONS[users_index].commands)
            if command.title == "Benutzer suchen"
        )
        getmouse.return_value = (
            0,
            layout.command_x + 3,
            layout.body_y + 2 + search_index,
            0,
            curses.BUTTON1_CLICKED,
        )
        self.app._handle_key(screen, curses.KEY_MOUSE)
        self.assertEqual(self.app.selection.command, search_index)
        self.assertEqual(self.app.current_command.title, "Benutzer suchen")
        prepare.assert_called_once_with(screen)

    def test_section_selection_wraps(self) -> None:
        self.app._handle_key(None, curses.KEY_UP)  # type: ignore[arg-type]
        self.assertEqual(self.app.selection.section, len(SECTIONS) - 1)

    def test_long_command_lists_scroll_around_selection(self) -> None:
        self.assertEqual(self.app._command_viewport(18, 0, 8), (0, 8))
        self.assertEqual(self.app._command_viewport(18, 9, 8), (5, 13))
        self.assertEqual(self.app._command_viewport(18, 17, 8), (10, 18))

    @patch("synadm_tui.app.App._prepare_command")
    def test_delete_shortcut_selects_gdpr_user_deletion(self, prepare) -> None:
        screen = Mock()
        self.app._handle_key(screen, ord("x"))
        self.assertEqual(self.app.current_command.title, "Benutzer löschen (GDPR)")
        prepare.assert_called_once_with(screen)

    @patch("synadm_tui.app.App._launch")
    @patch("synadm_tui.app.App._confirm", return_value=True)
    @patch("synadm_tui.app.App._prompt", return_value="@testuser:example.org")
    def test_gdpr_user_deletion_requires_confirmation_and_launches_exact_command(
        self, _prompt, confirm, launch
    ) -> None:
        self.app._select_command("Benutzer", "Benutzer löschen (GDPR)")
        self.app._prepare_command(Mock())
        expected = ["user", "deactivate", "--gdpr-erase", "@testuser:example.org"]
        confirm.assert_called_once_with(ANY, expected)
        launch.assert_called_once_with(expected)

    @patch("synadm_tui.app.App._launch")
    @patch("synadm_tui.app.App._confirm", return_value=False)
    @patch("synadm_tui.app.App._prompt", return_value="@testuser:example.org")
    def test_cancelled_gdpr_user_deletion_does_not_launch(self, _prompt, _confirm, launch) -> None:
        self.app._select_command("Benutzer", "Benutzer löschen (GDPR)")
        self.app._prepare_command(Mock())
        launch.assert_not_called()
        self.assertEqual(self.app.status, "Destruktive Aktion abgebrochen")

    def test_dangerous_target_requires_exact_reentry(self) -> None:
        args = ["user", "deactivate", "--gdpr-erase", "@alice:example.org"]
        self.assertEqual(self.app._typed_confirmation_target(args), "@alice:example.org")
        with patch.object(self.app, "_prompt", return_value="@bob:example.org"):
            self.assertFalse(self.app._confirm_typed_target(Mock(), "@alice:example.org"))
        self.assertEqual(
            self.app._typed_confirmation_target(["media", "delete", "--media-id", "abcdef123"]),
            "abcdef123",
        )

    def test_write_operations_have_read_only_verification(self) -> None:
        self.assertEqual(
            self.app._verification_args(["user", "suspend", "@alice:example.org"]),
            ["user", "details", "@alice:example.org"],
        )
        self.assertEqual(
            self.app._verification_args(["room", "block", "!room:example.org"]),
            ["room", "block-status", "!room:example.org"],
        )
        self.assertEqual(
            self.app._verification_args(["room", "join", "!room:example.org", "@alice:example.org"]),
            ["room", "members", "!room:example.org"],
        )

    def test_table_filter_and_sort_shortcuts_update_view(self) -> None:
        self.app.table_view = TableView([
            {"name": "@zoe:example.org", "admin": False},
            {"name": "@alice:example.org", "admin": True},
        ])
        with patch.object(self.app, "_prompt", return_value="alice"):
            self.app._handle_key(Mock(), ord("v"))
        self.assertEqual(self.app.table_view.filter_text, "alice")
        self.assertEqual(len(self.app.table_view.visible_rows()), 1)
        with patch.object(self.app, "_select_dialog_option", return_value="admin"):
            self.app._handle_key(Mock(), ord("s"))
        self.assertEqual(self.app.table_view.sort_key, "admin")

    def test_table_focus_moves_rows_and_opens_user_menu(self) -> None:
        self.app.table_view = TableView([
            {"name": "@alice:example.org"},
            {"name": "@zoe:example.org"},
        ])
        self.app.focus = "table"
        self.app._handle_key(Mock(), curses.KEY_DOWN)
        self.assertEqual(self.app.table_view.selected_user_id(), "@zoe:example.org")
        with patch.object(self.app, "_open_user_context_menu") as menu:
            screen = Mock()
            self.app._handle_key(screen, curses.KEY_ENTER)
        menu.assert_called_once_with(screen)

    def test_user_context_menu_prefills_selected_matrix_id(self) -> None:
        self.app.table_view = TableView([{"name": "@alice:example.org", "admin": False}])
        screen = Mock()
        with (
            patch.object(self.app, "_select_dialog_option", return_value="Benutzerdetails"),
            patch.object(self.app, "_prepare_command") as prepare,
        ):
            self.app._open_user_context_menu(screen)
        self.assertEqual(self.app.current_command.title, "Benutzerdetails")
        prepare.assert_called_once_with(screen, {"Benutzer-ID": "@alice:example.org"})

    def test_context_menu_rejects_non_user_table_row(self) -> None:
        self.app.table_view = TableView([{"room_id": "!room:example.org"}])
        with patch.object(self.app, "_select_dialog_option") as dialog:
            self.app._open_user_context_menu(Mock())
        dialog.assert_not_called()
        self.assertIn("keine Matrix-Benutzer-ID", self.app.status)

    @patch("synadm_tui.app.curses.getmouse")
    def test_mouse_selects_table_user_and_double_click_opens_menu(self, getmouse) -> None:
        self.app.table_view = TableView([
            {"name": "@alice:example.org"},
            {"name": "@zoe:example.org"},
        ])
        screen = Mock()
        screen.getmaxyx.return_value = (40, 140)
        layout = self.app._panel_layout(40, 140)
        assert layout is not None
        output_x = layout.command_x + layout.command_width + 1
        getmouse.return_value = (
            0,
            output_x + 3,
            layout.body_y + 6,
            0,
            curses.BUTTON1_CLICKED,
        )
        self.app._handle_key(screen, curses.KEY_MOUSE)
        self.assertEqual(self.app.focus, "table")
        self.assertEqual(self.app.table_view.selected_user_id(), "@zoe:example.org")

        getmouse.return_value = (
            0,
            output_x + 3,
            layout.body_y + 5,
            0,
            curses.BUTTON1_DOUBLE_CLICKED,
        )
        with patch.object(self.app, "_open_user_context_menu") as menu:
            self.app._handle_key(screen, curses.KEY_MOUSE)
        menu.assert_called_once_with(screen)

    @patch("synadm_tui.app.App._prepare_command")
    def test_room_create_shortcut_selects_assistant(self, prepare) -> None:
        screen = Mock()
        self.app._handle_key(screen, ord("a"))
        self.assertEqual(self.app.current_command.title, "Raum anlegen")
        prepare.assert_called_once_with(screen)

    def test_room_creation_wizard_builds_confirmed_matrix_api_command(self) -> None:
        screen = Mock()
        with (
            patch.object(self.app, "_prompt", side_effect=[
                "Projekt Alpha",
                "projekt-alpha",
                "Interne Planung",
                "@alice:example.org, @bob:example.org",
            ]),
            patch.object(
                self.app,
                "_select_dialog_option",
                side_effect=["private", "trusted_private_chat"],
            ),
            patch.object(self.app, "_dialog_yes_no", return_value=False),
            patch.object(self.app, "_confirm_room_creation", return_value=True) as confirm,
            patch.object(self.app, "_launch") as launch,
        ):
            self.app._select_command("Räume", "Raum anlegen")
            self.app._prepare_command(screen)

        creation = confirm.call_args.args[1]
        self.assertEqual(creation.name, "Projekt Alpha")
        command = launch.call_args.args[0]
        self.assertEqual(command[:6], [
            "matrix", "raw", "client/v3/createRoom", "--method", "post", "--data",
        ])
        payload = json.loads(command[6])
        self.assertEqual(payload["invite"], ["@alice:example.org", "@bob:example.org"])
        self.assertFalse(payload["creation_content"]["m.federate"])

    def test_cancelled_room_creation_does_not_launch(self) -> None:
        with (
            patch.object(self.app, "_prompt", return_value=None),
            patch.object(self.app, "_launch") as launch,
        ):
            self.app._create_room_wizard(Mock())
        launch.assert_not_called()
        self.assertEqual(self.app.status, "Raumerstellung abgebrochen")

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

    @patch("synadm_tui.app.App._prompt")
    def test_command_assistant_can_return_to_previous_field(self, prompt) -> None:
        prompt.side_effect = ["alice", WIZARD_BACK, "bob", "25"]
        search = next(
            command for section in SECTIONS for command in section.commands
            if command.argv == ("user", "search")
        )
        self.assertEqual(
            self.app._command_assistant(None, search),  # type: ignore[arg-type]
            ["bob", "--limit", "25"],
        )


if __name__ == "__main__":
    unittest.main()
