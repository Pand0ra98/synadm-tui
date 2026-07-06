import unittest

from synadm_tui.catalog import SECTIONS
from synadm_tui.command_help import DESCRIPTIONS, command_info


class CommandHelpTests(unittest.TestCase):
    def test_every_command_has_description_example_and_access_mode(self) -> None:
        for section in SECTIONS:
            for command in section.commands:
                info = command_info(command)
                self.assertTrue(info.description, command.title)
                self.assertTrue(info.example, command.title)
                self.assertIsInstance(info.writes, bool)
                self.assertIn(command.title, DESCRIPTIONS)


if __name__ == "__main__":
    unittest.main()
