import unittest

from synadm_tui.terminal_image import (
    kitty_delete_sequence,
    kitty_render_sequence,
    supports_kitty_graphics,
    theme_image_path,
)


class TerminalImageTests(unittest.TestCase):
    def test_detects_supported_terminals_without_false_positive(self) -> None:
        self.assertTrue(supports_kitty_graphics({"TERM": "xterm-kitty"}))
        self.assertTrue(supports_kitty_graphics({"TERM_PROGRAM": "WezTerm"}))
        self.assertFalse(supports_kitty_graphics({"TERM": "xterm-256color"}))

    def test_render_sequence_contains_png_transfer_and_placement(self) -> None:
        sequence = kitty_render_sequence(b"png-data", 3, 4, 10, 18)
        self.assertIn(b"\x1b[3;4H", sequence)
        self.assertIn(b"f=100", sequence)
        self.assertIn(b"c=18,r=10", sequence)
        self.assertIn(b"z=1", sequence)
        self.assertIn(b"a=d", kitty_delete_sequence())

    def test_theme_pngs_are_packaged(self) -> None:
        for theme in ("thuringia", "cyberspace", "hacker"):
            path = theme_image_path(theme)
            self.assertIsNotNone(path)
            assert path is not None
            self.assertTrue(path.is_file())
            self.assertEqual(path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
        self.assertIsNone(theme_image_path("matrix"))


if __name__ == "__main__":
    unittest.main()
