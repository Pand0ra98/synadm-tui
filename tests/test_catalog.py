import unittest

from synadm_tui.catalog import SECTIONS


class CatalogTests(unittest.TestCase):
    def test_catalog_has_unique_sections_and_a_safe_confirmation_boundary(self) -> None:
        self.assertEqual(len({section.title for section in SECTIONS}), len(SECTIONS))
        self.assertIn("Moderation", {section.title for section in SECTIONS})
        commands = [command for section in SECTIONS for command in section.commands]
        self.assertTrue(any(command.dangerous for command in commands))
        self.assertTrue(any(not command.argv for command in commands))
        room_delete = next(command for command in commands if command.title == "Raum löschen")
        self.assertTrue(room_delete.dangerous)
        user_delete = next(command for command in commands if command.title == "Benutzer löschen (GDPR)")
        self.assertEqual(user_delete.argv, ("user", "deactivate", "--gdpr-erase"))
        self.assertTrue(user_delete.dangerous)
        user_create = next(command for command in commands if command.title == "Benutzer anlegen")
        self.assertEqual(user_create.action, "create_user")
        self.assertTrue(user_create.dangerous)
        room_create = next(command for command in commands if command.title == "Raum anlegen")
        self.assertEqual(room_create.action, "create_room")
        self.assertTrue(room_create.dangerous)
        installer = next(command for command in commands if command.action == "install_synadm")
        self.assertTrue(installer.dangerous)
        self.assertEqual(installer.argv, ())
        package_actions = {command.action for command in commands}
        self.assertIn("choose_theme", package_actions)
        self.assertIn("configure_synadm", package_actions)
        self.assertIn("create_user", package_actions)
        self.assertIn("uninstall_synadm", package_actions)
        self.assertIn("uninstall_pipx", package_actions)
        self.assertIn("create_room", package_actions)
        self.assertIn("show_audit", package_actions)
        self.assertIn("toggle_demo", package_actions)


if __name__ == "__main__":
    unittest.main()
