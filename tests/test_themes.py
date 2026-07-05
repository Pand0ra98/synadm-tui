import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from synadm_tui.app import App, THEMES, THEMES_BY_KEY
from synadm_tui.edition import Edition, STANDARD_EDITION


class ThemeTests(unittest.TestCase):
    def test_all_themes_have_unique_keys_complete_palettes_and_art(self) -> None:
        self.assertEqual(len({theme.key for theme in THEMES}), 5)
        for theme in THEMES:
            self.assertEqual(len(theme.palette), 9)
            self.assertTrue(theme.art)
            self.assertTrue(theme.ready_label)

    def test_saved_theme_is_loaded_from_xdg_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": directory}):
                self.assertTrue(App._save_theme(THEMES_BY_KEY["matrix"]))
                self.assertEqual(App._load_theme().key, "matrix")

    def test_external_edition_requires_registered_theme(self) -> None:
        external = Edition("external", "External", "external", "external", ("external",))
        self.assertNotIn("thuringia", STANDARD_EDITION.theme_keys)
        with self.assertRaisesRegex(ValueError, "Theme nicht registriert"):
            App(Mock(), external)


if __name__ == "__main__":
    unittest.main()
