import json
import unittest

from synadm_tui.table_view import TableView


class TableViewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.table = TableView.from_json(json.dumps({"users": [
            {"name": "@zoe:example.org", "admin": False, "displayname": "Zoe"},
            {"name": "@alice:example.org", "admin": True, "displayname": "Alice"},
        ]}))
        assert self.table is not None

    def test_extracts_filters_and_sorts_rows(self) -> None:
        self.table.filter_text = "alice"
        self.assertEqual(len(self.table.visible_rows()), 1)
        self.assertEqual(self.table.visible_rows()[0]["name"], "@alice:example.org")
        self.table.filter_text = ""
        self.table.select_sort("displayname")
        self.assertEqual(self.table.visible_rows()[0]["displayname"], "Alice")
        self.table.select_sort("displayname")
        self.assertEqual(self.table.visible_rows()[0]["displayname"], "Zoe")

    def test_renders_within_requested_width(self) -> None:
        lines = self.table.render(48)
        self.assertIn("Tabelle 2/2", lines[0])
        self.assertTrue(all(len(line) <= 48 for line in lines))
        self.assertTrue(lines[3].startswith("▶ "))

    def test_row_selection_finds_matrix_user_id(self) -> None:
        self.table.move(1)
        self.assertEqual(self.table.selected_user_id(), "@zoe:example.org")
        self.table.move(-1)
        self.assertEqual(self.table.selected_user_id(), "@alice:example.org")

    def test_non_json_and_scalar_json_do_not_create_table(self) -> None:
        self.assertIsNone(TableView.from_json("not json"))
        self.assertIsNone(TableView.from_json('{"server_version":"1.2"}'))

    def test_scalar_membership_list_becomes_single_column_table(self) -> None:
        table = TableView.from_json('{"joined_rooms":["#one:example.org","#two:example.org"]}')
        assert table is not None
        self.assertEqual(table.columns, ["joined_rooms"])
        self.assertEqual(len(table.rows), 2)

    def test_extracts_multiple_json_results_from_search_output(self) -> None:
        text = (
            "Suchergebnis klein:\n"
            '{"users":[{"name":"@alice:example.org"}]}\n'
            "Suchergebnis groß:\n"
            '{"users":[{"name":"@Alice:example.org"}]}\n'
        )
        table = TableView.from_json(text)
        assert table is not None
        self.assertEqual(len(table.rows), 2)


if __name__ == "__main__":
    unittest.main()
