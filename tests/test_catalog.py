import unittest

from synadm_tui.catalog import SECTIONS


class CatalogTests(unittest.TestCase):
    def test_catalog_has_unique_sections_and_a_safe_confirmation_boundary(self) -> None:
        self.assertEqual(len({section.title for section in SECTIONS}), len(SECTIONS))
        commands = [command for section in SECTIONS for command in section.commands]
        self.assertTrue(any(command.dangerous for command in commands))
        self.assertTrue(any(not command.argv for command in commands))
        room_delete = next(command for command in commands if command.title == "Raum löschen")
        self.assertTrue(room_delete.dangerous)
        installer = next(command for command in commands if command.action == "install_synadm")
        self.assertTrue(installer.dangerous)
        self.assertEqual(installer.argv, ())
        package_actions = {command.action for command in commands}
        self.assertIn("choose_theme", package_actions)
        self.assertIn("configure_synadm", package_actions)
        self.assertIn("uninstall_synadm", package_actions)
        self.assertIn("uninstall_pipx", package_actions)


if __name__ == "__main__":
    unittest.main()
