from __future__ import annotations

import unittest

import synadm_tui
from synadm_tui.app import App
from synadm_tui.runner import SynadmRunner
from synadm_tui_thueringen import __version__
from synadm_tui_thueringen.theme import THURINGIA_EDITION, THURINGIA_THEME


class ThueringenEditionTests(unittest.TestCase):
    def test_core_and_overlay_versions_match(self) -> None:
        self.assertEqual(__version__, synadm_tui.__version__)

    def test_theme_assets_are_packaged_and_complete(self) -> None:
        self.assertTrue(THURINGIA_THEME.image_path.is_file())
        self.assertTrue(THURINGIA_THEME.block_path.is_file())
        self.assertEqual(len(THURINGIA_THEME.palette), 9)

    def test_core_accepts_thueringen_edition(self) -> None:
        app = App(SynadmRunner("not-installed"), THURINGIA_EDITION, (THURINGIA_THEME,))
        self.assertEqual(app.theme.key, "thuringia")
        self.assertEqual(app.edition.binary_name, "synadm-tui-thueringen")


if __name__ == "__main__":
    unittest.main()
