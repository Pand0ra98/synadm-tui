import os
import tempfile
import unittest
from unittest.mock import patch

from synadm_tui.app import App, THEMES
from synadm_tui.edition import STANDARD_EDITION, THURINGIA_EDITION


class ThemeTests(unittest.TestCase):
    def test_all_themes_have_unique_keys_complete_palettes_and_art(self) -> None:
        self.assertEqual(len({theme.key for theme in THEMES}), 6)
        for theme in THEMES:
            self.assertEqual(len(theme.palette), 9)
            self.assertTrue(theme.art)
            self.assertTrue(theme.ready_label)

    def test_saved_theme_is_loaded_from_xdg_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": directory}):
                self.assertTrue(App._save_theme(THEMES[2]))
                self.assertEqual(App._load_theme().key, "matrix")

    def test_thuringia_theme_is_exclusive_to_thuringia_edition(self) -> None:
        self.assertNotIn("thuringia", STANDARD_EDITION.theme_keys)
        self.assertIn("thuringia", THURINGIA_EDITION.theme_keys)
        self.assertEqual(THURINGIA_EDITION.default_theme, "thuringia")


if __name__ == "__main__":
    unittest.main()
