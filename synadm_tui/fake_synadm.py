"""Local demo backend that emulates a useful subset of synadm.

The demo backend is intentionally separate from the TUI logic. It stores a tiny
Matrix-like world in a JSON file and returns JSON shaped for the normal table
renderer, making interactive development possible without a Synapse server.
"""

from __future__ import annotations

import json
import os
import shlex
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .runner import Result, SynadmRunner

SERVER_NAME = "demo.local"


@dataclass(frozen=True, slots=True)
class DemoResponse:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class FakeSynadmRunner(SynadmRunner):
    """A ``SynadmRunner`` compatible in-process demo backend."""

    def __init__(self, state_path: str | Path | None = None, timeout: float = 60.0) -> None:
        super().__init__("fake-synadm", None, timeout)
        self.state_path = demo_state_path(state_path)

    @property
    def available(self) -> bool:
        return True

    @property
    def demo_mode(self) -> bool:
        return True

    def build_command(self, args: Sequence[str], *, structured: bool = True) -> list[str]:
        command = ["fake-synadm", "--batch"]
        if structured and "--help" not in args and "-h" not in args and "config" not in args:
            command += ["--output", "json"]
        command.extend(args)
        return command

    def run(self, args: Sequence[str], *, structured: bool = True) -> Result:
        started = time.monotonic()
        response = execute(args, self.state_path, structured=structured)
        return Result(
            tuple(self.build_command(args, structured=structured)),
            response.returncode,
            response.stdout,
            response.stderr,
            time.monotonic() - started,
        )


def demo_state_path(value: str | Path | None = None) -> Path:
    if value:
        return Path(value).expanduser()
    root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return root / "synadm-tui" / "demo-server.json"


def execute(args: Sequence[str], state_path: Path, *, structured: bool = True) -> DemoResponse:
    state = _load_state(state_path)
    command = tuple(args)
    if not command:
        return _ok({"demo": True, "message": "fake synadm backend"})
    if "--help" in command or "-h" in command:
        return DemoResponse(0, _help_text())
    if command == ("config", "--help"):
        return DemoResponse(0, "Demo-Modus: keine echte synadm-Konfiguration erforderlich.\n")

    try:
        if command == ("version",):
            return _ok({"server_version": "demo-synapse-1.0", "demo": True})
        if command[0] == "user":
            response = _handle_user(state, command[1:])
        elif command[0] == "room":
            response = _handle_room(state, command[1:])
        elif command[0] == "matrix":
            response = _handle_matrix(state, command[1:])
        elif command[0] == "regtok":
            response = _handle_regtok(state, command[1:])
        else:
            return _error(f"Demo-Backend kennt diesen Befehl noch nicht: {' '.join(command)}")
    except DemoError as error:
        return _error(str(error))

    _save_state(state_path, state)
    if structured:
        return _ok(response)
    return DemoResponse(0, json.dumps(response, ensure_ascii=False, indent=2) + "\n")


def main(argv: list[str] | None = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    state_path = demo_state_path(os.environ.get("SYNADM_TUI_DEMO_STATE"))
    command = _strip_global_options(raw_args)
    response = execute(command, state_path)
    if response.stdout:
        print(response.stdout, end="")
    if response.stderr:
        print(response.stderr, end="", file=sys.stderr)
    return response.returncode


class DemoError(ValueError):
    pass


def _strip_global_options(args: list[str]) -> list[str]:
    result: list[str] = []
    skip_next = False
    for index, item in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if item in {"--batch"}:
            continue
        if item in {"--output", "--config-file"}:
            skip_next = index + 1 < len(args)
            continue
        result.append(item)
    return result


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "users": {},
            "rooms": {},
            "regtoks": {},
            "next_room": 1,
        }
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DemoError(f"Demo-Zustand kann nicht gelesen werden: {error}") from error


def _save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _ok(payload: object) -> DemoResponse:
    return DemoResponse(0, json.dumps(payload, ensure_ascii=False) + "\n")


def _error(message: str) -> DemoResponse:
    return DemoResponse(1, "", message + "\n")


def _handle_user(state: dict[str, Any], args: tuple[str, ...]) -> dict[str, Any]:
    if not args:
        raise DemoError("user-Unterbefehl fehlt.")
    users: dict[str, dict[str, Any]] = state.setdefault("users", {})
    action, rest = args[0], args[1:]
    if action == "list":
        return {"users": sorted(users.values(), key=lambda user: user["name"])}
    if action == "search":
        needle = " ".join(item for item in rest if not item.startswith("--")).casefold()
        found = [
            user for user in users.values()
            if needle in user["name"].casefold() or needle in str(user.get("displayname", "")).casefold()
        ]
        return {"users": sorted(found, key=lambda user: user["name"])}
    if action == "details":
        return _user_details(users, _required_arg(rest, "Benutzer-ID"))
    if action == "modify":
        user_id = _required_arg(rest, "Benutzer-ID")
        options = _parse_options(rest[1:])
        user = users.setdefault(user_id, _new_user(user_id))
        if "display-name" in options:
            user["displayname"] = options["display-name"]
        if "password" in options:
            user["password_set"] = True
        if "threepid" in options:
            threepid = options["threepid"]
            if len(threepid) >= 2 and threepid[0] == "email":
                user["email"] = threepid[1]
        if "admin" in options:
            user["admin"] = True
        if "no-admin" in options:
            user["admin"] = False
        if "user-type" in options:
            user["user_type"] = options["user-type"]
        if "lock" in options:
            user["locked"] = True
        if "unlock" in options:
            user["locked"] = False
        if "deactivate" in options:
            user["deactivated"] = True
        if "avatar-url" in options:
            user["avatar_url"] = options["avatar-url"]
        return {"user": user, "created_or_updated": user_id}
    if action == "password":
        user = _existing_user(users, _required_arg(rest, "Benutzer-ID"))
        user["password_set"] = True
        return {"user": user, "password_changed": True}
    if action == "deactivate":
        erase = "--gdpr-erase" in rest
        user_id = next((item for item in rest if item.startswith("@")), "")
        user = _existing_user(users, user_id or _required_arg(rest, "Benutzer-ID"))
        user["deactivated"] = True
        user["erased"] = erase
        return {"user": user, "deactivated": True, "gdpr_erase": erase}
    if action == "suspend":
        user_id = next((item for item in rest if item.startswith("@")), "")
        user = _existing_user(users, user_id or _required_arg(rest, "Benutzer-ID"))
        user["suspended"] = "--unsuspend" not in rest
        return {"user": user}
    if action == "shadow-ban":
        user_id = next((item for item in rest if item.startswith("@")), "")
        user = _existing_user(users, user_id or _required_arg(rest, "Benutzer-ID"))
        user["shadow_banned"] = "--unban" not in rest
        return {"user": user}
    if action in {"membership", "media", "whois"}:
        user = _existing_user(users, _required_arg(rest, "Benutzer-ID"))
        return {"user": user, "rooms": list(user.get("rooms", [])), "media": []}
    raise DemoError(f"user-Unterbefehl wird im Demo-Modus noch nicht unterstützt: {action}")


def _handle_room(state: dict[str, Any], args: tuple[str, ...]) -> dict[str, Any]:
    if not args:
        raise DemoError("room-Unterbefehl fehlt.")
    rooms: dict[str, dict[str, Any]] = state.setdefault("rooms", {})
    action, rest = args[0], args[1:]
    if action == "list":
        return {"rooms": sorted(rooms.values(), key=lambda room: room["room_id"])}
    if action == "search":
        needle = " ".join(item for item in rest if not item.startswith("--")).casefold()
        return {"rooms": [room for room in rooms.values() if needle in json.dumps(room).casefold()]}
    if action in {"details", "members", "block-status"}:
        room = _existing_room(rooms, _required_arg(rest, "Raum-ID"))
        if action == "members":
            return {"members": [{"name": user_id} for user_id in room.get("members", [])]}
        return {"room": room}
    if action == "join":
        room = _existing_room(rooms, _required_arg(rest, "Raum-ID"))
        user_id = _required_arg(rest[1:], "Benutzer-ID")
        members = room.setdefault("members", [])
        if user_id not in members:
            members.append(user_id)
        return {"room": room, "joined": user_id}
    if action == "make-admin":
        room = _existing_room(rooms, _required_arg(rest, "Raum-ID"))
        user_id = _option_value(rest, "--user-id") or "demo-admin"
        admins = room.setdefault("admins", [])
        if user_id not in admins:
            admins.append(user_id)
        return {"room": room, "admin": user_id}
    if action == "block":
        room = _existing_room(rooms, _required_arg(rest, "Raum-ID"))
        room["blocked"] = "--unblock" not in rest
        return {"room": room}
    if action in {"resolve", "state", "power-levels", "delete", "delete-status", "purge-empty"}:
        return {"result": "Demo-Aktion erfolgreich", "args": list(args)}
    raise DemoError(f"room-Unterbefehl wird im Demo-Modus noch nicht unterstützt: {action}")


def _handle_matrix(state: dict[str, Any], args: tuple[str, ...]) -> dict[str, Any]:
    if args[:2] != ("raw", "client/v3/createRoom"):
        raise DemoError("Im Demo-Modus ist nur matrix raw client/v3/createRoom implementiert.")
    data = _option_value(args, "--data")
    payload = json.loads(data) if data else {}
    room_id = f"!demo{state.get('next_room', 1)}:{SERVER_NAME}"
    state["next_room"] = int(state.get("next_room", 1)) + 1
    alias = payload.get("room_alias_name")
    room = {
        "room_id": room_id,
        "name": payload.get("name") or alias or room_id,
        "canonical_alias": f"#{alias}:{SERVER_NAME}" if alias else "",
        "topic": payload.get("topic", ""),
        "visibility": payload.get("visibility", "private"),
        "preset": payload.get("preset", ""),
        "members": list(payload.get("invite", [])),
        "blocked": False,
    }
    state.setdefault("rooms", {})[room_id] = room
    return {"room_id": room_id, "room_alias": room["canonical_alias"], "room": room}


def _handle_regtok(state: dict[str, Any], args: tuple[str, ...]) -> dict[str, Any]:
    tokens: dict[str, dict[str, Any]] = state.setdefault("regtoks", {})
    action = args[0] if args else "list"
    if action == "list":
        return {"results": sorted(tokens.values(), key=lambda token: token["token"])}
    if action == "new":
        token = f"DEMO{len(tokens) + 1:04d}"
        tokens[token] = {"token": token, "uses_allowed": None, "pending": 0, "completed": 0}
        return {"token": tokens[token]}
    if action == "details":
        token = _required_arg(args[1:], "Token")
        return {"token": tokens.get(token, {"token": token, "missing": True})}
    if action == "delete":
        token = _required_arg(args[1:], "Token")
        tokens.pop(token, None)
        return {"deleted": token}
    if action == "update":
        token = _required_arg(args[1:], "Token")
        tokens.setdefault(token, {"token": token})
        return {"token": tokens[token], "updated": True}
    raise DemoError(f"regtok-Unterbefehl wird im Demo-Modus noch nicht unterstützt: {action}")


def _new_user(user_id: str) -> dict[str, Any]:
    if not user_id.startswith("@") or ":" not in user_id:
        raise DemoError(f"Ungültige Matrix-ID: {user_id}")
    return {
        "name": user_id,
        "user_id": user_id,
        "displayname": "",
        "admin": False,
        "deactivated": False,
        "locked": False,
        "suspended": False,
        "shadow_banned": False,
        "user_type": "regular",
        "email": "",
        "rooms": [],
    }


def _user_details(users: dict[str, dict[str, Any]], user_id: str) -> dict[str, Any]:
    return {"user": _existing_user(users, user_id)}


def _existing_user(users: dict[str, dict[str, Any]], user_id: str) -> dict[str, Any]:
    if user_id not in users:
        raise DemoError(f"Demo-Benutzer existiert nicht: {user_id}")
    return users[user_id]


def _existing_room(rooms: dict[str, dict[str, Any]], room_id: str) -> dict[str, Any]:
    if room_id not in rooms:
        raise DemoError(f"Demo-Raum existiert nicht: {room_id}")
    return rooms[room_id]


def _required_arg(args: tuple[str, ...], label: str) -> str:
    for item in args:
        if not item.startswith("--"):
            return item
    raise DemoError(f"{label} fehlt.")


def _parse_options(args: tuple[str, ...]) -> dict[str, Any]:
    options: dict[str, Any] = {}
    index = 0
    while index < len(args):
        item = args[index]
        if not item.startswith("--"):
            index += 1
            continue
        key = item.removeprefix("--")
        if key == "threepid":
            options[key] = list(args[index + 1:index + 3])
            index += 3
        elif index + 1 < len(args) and not args[index + 1].startswith("--"):
            options[key] = args[index + 1]
            index += 2
        else:
            options[key] = True
            index += 1
    return options


def _option_value(args: tuple[str, ...], option: str) -> str:
    try:
        index = args.index(option)
    except ValueError:
        return ""
    if index + 1 >= len(args):
        return ""
    return args[index + 1]


def _help_text() -> str:
    return (
        "fake-synadm Demo-Backend\n\n"
        "Unterstützt lokal: version, user list/search/details/modify/deactivate,\n"
        "room list/search/details/members/join/block und matrix raw client/v3/createRoom.\n\n"
        "Beispiel: "
        + shlex.join(["fake-synadm", "--batch", "--output", "json", "user", "list"])
        + "\n"
    )


if __name__ == "__main__":
    raise SystemExit(main())
