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

    def test_gdpr_user_deletion_only_requests_required_user_id(self) -> None:
        fields = fields_for(("user", "deactivate", "--gdpr-erase"), "")
        self.assertEqual(len(fields), 1)
        self.assertEqual(fields[0].label, "Benutzer-ID")
        self.assertTrue(fields[0].required)

    def test_moderation_and_device_forms_are_guided(self) -> None:
        suspend = fields_for(("user", "suspend"), "")
        self.assertEqual(len(suspend), 1)
        self.assertTrue(suspend[0].required)
        devices = fields_for(("user", "prune-devices"), "")
        self.assertEqual(devices[1].prefix, ("--min-days",))
        self.assertEqual(devices[2].prefix, ("--min-surviving",))

    def test_room_join_and_admin_forms_have_structured_ids(self) -> None:
        join = fields_for(("room", "join"), "")
        self.assertEqual([field.label for field in join], ["Raum-ID oder Alias", "Benutzer-ID"])
        self.assertTrue(all(field.required for field in join))
        make_admin = fields_for(("room", "make-admin"), "")
        self.assertEqual(make_admin[1].prefix, ("--user-id",))

    def test_unknown_advanced_command_keeps_raw_options(self) -> None:
        fields = fields_for(("media", "quarantine"), "OPTIONEN")
        self.assertEqual(len(fields), 1)
        self.assertTrue(fields[0].raw)

    def test_command_without_arguments_needs_no_dialog(self) -> None:
        self.assertEqual(fields_for(("version",), ""), ())


if __name__ == "__main__":
    unittest.main()
