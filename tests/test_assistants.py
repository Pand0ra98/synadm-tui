import unittest

from synadm_tui.assistants import fields_for


class AssistantTests(unittest.TestCase):
    def test_user_search_has_guided_search_and_limit_fields(self) -> None:
        fields = fields_for(("user", "search"), "")
        self.assertEqual(fields[0].label, "Suchbegriff")
        self.assertTrue(fields[0].required)
        self.assertEqual(fields[1].prefix, ("--limit",))

    def test_password_field_is_secret(self) -> None:
        fields = fields_for(("user", "password"), "")
        password = next(field for field in fields if field.label == "Neues Passwort")
        self.assertTrue(password.secret)
        self.assertTrue(password.required)

    def test_unknown_advanced_command_keeps_raw_options(self) -> None:
        fields = fields_for(("media", "quarantine"), "OPTIONEN")
        self.assertEqual(len(fields), 1)
        self.assertTrue(fields[0].raw)

    def test_command_without_arguments_needs_no_dialog(self) -> None:
        self.assertEqual(fields_for(("version",), ""), ())


if __name__ == "__main__":
    unittest.main()
