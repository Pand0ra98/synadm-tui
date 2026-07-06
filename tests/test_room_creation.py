import json
import unittest

from synadm_tui.room_creation import RoomCreation, RoomCreationError, parse_invitees


class RoomCreationTests(unittest.TestCase):
    def test_builds_matrix_create_room_command_without_token(self) -> None:
        creation = RoomCreation(
            name="Projekt Alpha",
            alias="projekt-alpha",
            topic="Interne Planung",
            visibility="private",
            preset="trusted_private_chat",
            invitees=("@alice:example.org", "@bob:example.org"),
            federated=False,
        )

        command = creation.command()
        self.assertEqual(command[:6], [
            "matrix", "raw", "client/v3/createRoom", "--method", "post", "--data",
        ])
        payload = json.loads(command[6])
        self.assertEqual(payload["name"], "Projekt Alpha")
        self.assertEqual(payload["room_alias_name"], "projekt-alpha")
        self.assertEqual(payload["invite"], ["@alice:example.org", "@bob:example.org"])
        self.assertFalse(payload["creation_content"]["m.federate"])
        self.assertNotIn("token", " ".join(command).lower())

    def test_optional_values_are_omitted(self) -> None:
        payload = RoomCreation(name="Minimal").payload()
        self.assertNotIn("room_alias_name", payload)
        self.assertNotIn("topic", payload)
        self.assertNotIn("invite", payload)

    def test_rejects_full_alias_and_invalid_invitee(self) -> None:
        with self.assertRaisesRegex(RoomCreationError, "lokalen Teil"):
            RoomCreation(name="Test", alias="#test:example.org").validate()
        with self.assertRaisesRegex(RoomCreationError, "Ungültige Matrix-ID"):
            RoomCreation(name="Test", invitees=("alice",)).validate()

    def test_parses_unique_comma_separated_invitees(self) -> None:
        self.assertEqual(
            parse_invitees("@alice:example.org, @bob:example.org, @alice:example.org"),
            ("@alice:example.org", "@bob:example.org"),
        )


if __name__ == "__main__":
    unittest.main()
