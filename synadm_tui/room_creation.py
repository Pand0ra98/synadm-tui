"""Validated Matrix room creation payloads for the guided TUI assistant."""

from __future__ import annotations

import json
from dataclasses import dataclass


VISIBILITIES = {"private", "public"}
PRESETS = {"private_chat", "trusted_private_chat", "public_chat"}


class RoomCreationError(ValueError):
    """Raised when room creation input cannot form a safe API request."""


@dataclass(frozen=True, slots=True)
class RoomCreation:
    name: str
    alias: str = ""
    topic: str = ""
    visibility: str = "private"
    preset: str = "private_chat"
    invitees: tuple[str, ...] = ()
    federated: bool = True

    def validate(self) -> None:
        if not self.name.strip():
            raise RoomCreationError("Der Raumname darf nicht leer sein.")
        if self.visibility not in VISIBILITIES:
            raise RoomCreationError("Die Sichtbarkeit muss private oder public sein.")
        if self.preset not in PRESETS:
            raise RoomCreationError("Unbekannte Raumvorlage.")
        alias = self.alias.strip()
        if alias and (alias.startswith("#") or ":" in alias or any(char.isspace() for char in alias)):
            raise RoomCreationError("Beim Alias nur den lokalen Teil ohne #, Server oder Leerzeichen eingeben.")
        for user_id in self.invitees:
            if not user_id.startswith("@") or ":" not in user_id or any(char.isspace() for char in user_id):
                raise RoomCreationError(f"Ungültige Matrix-ID für Einladung: {user_id}")

    def payload(self) -> dict[str, object]:
        self.validate()
        data: dict[str, object] = {
            "name": self.name.strip(),
            "visibility": self.visibility,
            "preset": self.preset,
            "creation_content": {"m.federate": self.federated},
        }
        if self.alias.strip():
            data["room_alias_name"] = self.alias.strip()
        if self.topic.strip():
            data["topic"] = self.topic.strip()
        if self.invitees:
            data["invite"] = list(self.invitees)
        return data

    def command(self) -> list[str]:
        encoded = json.dumps(self.payload(), ensure_ascii=False, separators=(",", ":"))
        return [
            "matrix",
            "raw",
            "client/v3/createRoom",
            "--method",
            "post",
            "--data",
            encoded,
        ]


def parse_invitees(value: str) -> tuple[str, ...]:
    """Parse comma-separated Matrix IDs while preserving order and removing duplicates."""
    invitees: list[str] = []
    for item in value.replace("\n", ",").split(","):
        user_id = item.strip()
        if user_id and user_id not in invitees:
            invitees.append(user_id)
    return tuple(invitees)
