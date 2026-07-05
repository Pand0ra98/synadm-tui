import unittest

from synadm_tui.block_art import load_block_cells, rgb_to_xterm


class BlockArtTests(unittest.TestCase):
    def test_generated_theme_grids_form_ten_terminal_rows(self) -> None:
        for theme in ("thuringia", "cyberspace", "hacker"):
            rows = load_block_cells(theme)
            self.assertIsNotNone(rows)
            assert rows is not None
            self.assertEqual(len(rows), 10)
            self.assertTrue(all(len(row) == 18 for row in rows))
            self.assertTrue(any(cell is not None for row in rows for cell in row))

    def test_unknown_theme_has_no_block_art(self) -> None:
        self.assertIsNone(load_block_cells("matrix"))

    def test_rgb_mapping_uses_xterm_256_palette(self) -> None:
        self.assertEqual(rgb_to_xterm(0, 0, 0), 16)
        self.assertEqual(rgb_to_xterm(255, 255, 255), 231)


if __name__ == "__main__":
    unittest.main()
