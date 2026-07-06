"""Field definitions for guided synadm command dialogs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Field:
    label: str
    hint: str
    prefix: tuple[str, ...] = ()
    required: bool = False
    raw: bool = False
    secret: bool = False


RAW_OPTIONS = Field("Weitere Optionen", "Optional, z. B. --limit 50", raw=True)
USER_ID = Field("Benutzer-ID", "@name:server.tld", required=True)
ROOM_ID = Field("Raum-ID oder Alias", "!raumid:server.tld oder #alias:server.tld", required=True)
TOKEN = Field("Token", "Registrierungstoken", required=True)
TASK_ID = Field("Vorgangs-ID", "Von Synapse zurückgegebene ID", required=True)


FORMS: dict[tuple[str, ...], tuple[Field, ...]] = {
    ("user", "list"): (
        Field("Namensfilter", "Optionaler Teil von ID oder Anzeigename", ("--name",)),
        Field("Limit", "Optional, Standard: 100", ("--limit",)),
        RAW_OPTIONS,
    ),
    ("user", "search"): (
        Field("Suchbegriff", "Name oder Teil einer Matrix-ID", required=True),
        Field("Limit", "Optional, Standard: 100", ("--limit",)),
    ),
    ("user", "details"): (USER_ID,),
    ("user", "modify"): (
        USER_ID,
        Field("Anzeigename", "Optional", ("--display-name",)),
        Field("Passwort", "Optional; Eingabe wird maskiert", ("--password",), secret=True),
        Field("E-Mail", "Optional", ("--threepid", "email")),
        RAW_OPTIONS,
    ),
    ("user", "password"): (
        USER_ID,
        Field("Neues Passwort", "Wird maskiert", ("--password",), required=True, secret=True),
        RAW_OPTIONS,
    ),
    ("user", "deactivate"): (USER_ID, RAW_OPTIONS),
    ("user", "deactivate", "--gdpr-erase"): (USER_ID,),
    ("user", "membership"): (USER_ID,),
    ("user", "media"): (
        USER_ID,
        Field("Limit", "Optional, Standard: 100", ("--limit",)),
        RAW_OPTIONS,
    ),
    ("user", "whois"): (USER_ID,),
    ("user", "suspend"): (USER_ID,),
    ("user", "suspend", "--unsuspend"): (USER_ID,),
    ("user", "shadow-ban"): (USER_ID,),
    ("user", "shadow-ban", "--unban"): (USER_ID,),
    ("user", "prune-devices", "--list-only"): (
        USER_ID,
        Field("Mindestalter in Tagen", "Optional, Standard: 90", ("--min-days",)),
        Field("Mindestens verbleibende Geräte", "Optional, Standard: 1", ("--min-surviving",)),
        Field("Bestimmte Geräte-ID", "Optional", ("--device-id",)),
    ),
    ("user", "prune-devices"): (
        USER_ID,
        Field("Mindestalter in Tagen", "Optional, Standard: 90", ("--min-days",)),
        Field("Mindestens verbleibende Geräte", "Optional, Standard: 1", ("--min-surviving",)),
        Field("Bestimmte Geräte-ID", "Optional", ("--device-id",)),
    ),
    ("user", "redact"): (USER_ID, RAW_OPTIONS),
    ("user", "redact-status"): (TASK_ID,),
    ("room", "list"): (
        Field("Namensfilter", "Optional", ("--name",)),
        Field("Limit", "Optional, Standard: 100", ("--limit",)),
        RAW_OPTIONS,
    ),
    ("room", "search"): (
        Field("Suchbegriff", "Raumname oder Alias", required=True),
        Field("Limit", "Optional", ("--limit",)),
    ),
    ("room", "resolve"): (ROOM_ID,),
    ("room", "details"): (ROOM_ID,),
    ("room", "members"): (ROOM_ID,),
    ("room", "join"): (ROOM_ID, USER_ID),
    ("room", "make-admin"): (
        ROOM_ID,
        Field("Benutzer-ID", "Optional; leer bedeutet konfigurierter Admin", ("--user-id",)),
    ),
    ("room", "state"): (ROOM_ID,),
    ("room", "block-status"): (ROOM_ID,),
    ("room", "block"): (ROOM_ID, RAW_OPTIONS),
    ("room", "block", "--unblock"): (ROOM_ID,),
    ("room", "delete"): (ROOM_ID, RAW_OPTIONS),
    ("room", "delete-status", "--room-id"): (ROOM_ID,),
    ("room", "purge-empty", "--dry-run"): (RAW_OPTIONS,),
    ("room", "purge-empty"): (RAW_OPTIONS,),
    ("media", "protect"): (Field("Medien-ID", "Lokale Medien-ID", required=True),),
    ("media", "delete", "--media-id"): (Field("Medien-ID", "Lokale Medien-ID", required=True),),
    ("regtok", "details"): (TOKEN,),
    ("regtok", "update"): (TOKEN, RAW_OPTIONS),
    ("regtok", "delete"): (TOKEN,),
    ("regtok", "new"): (RAW_OPTIONS,),
    ("history", "purge"): (ROOM_ID, RAW_OPTIONS),
    ("history", "purge-status"): (TASK_ID,),
}


def fields_for(argv: tuple[str, ...], hint: str) -> tuple[Field, ...]:
    if argv in FORMS:
        return FORMS[argv]
    if not argv:
        return (Field("synadm-Befehl", hint, required=True, raw=True),)
    if hint:
        return (Field("Argumente und Optionen", hint, raw=True),)
    return ()
