from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from synadm_tui.file_browser import list_entries


class FileBrowserTests(unittest.TestCase):
    def test_lists_directories_first_and_filters_non_csv_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "unterordner").mkdir()
            (root / "users.CSV").write_text("user\nalice\n", encoding="utf-8")
            (root / "notes.txt").write_text("ignore", encoding="utf-8")
            entries = list_entries(root)
            self.assertEqual([entry.path.name for entry in entries], ["unterordner", "users.CSV"])
            self.assertTrue(entries[0].is_dir)
            self.assertFalse(entries[1].is_dir)

    def test_can_list_all_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "users.txt").write_text("data", encoding="utf-8")
            self.assertEqual(len(list_entries(root, csv_only=False)), 1)


if __name__ == "__main__":
    unittest.main()
