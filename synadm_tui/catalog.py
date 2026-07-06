"""Command catalogue displayed by the TUI."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Command:
    title: str
    argv: tuple[str, ...]
    hint: str = ""
    dangerous: bool = False
    action: str | None = None


@dataclass(frozen=True, slots=True)
class Section:
    title: str
    commands: tuple[Command, ...]


SECTIONS = (
    Section(
        "Übersicht",
        (
            Command("Serverversion", ("version",)),
            Command("synadm-Hilfe", ("--help",)),
            Command("Konfigurationshilfe", ("config", "--help")),
        ),
    ),
    Section(
        "Benutzer",
        (
            Command("Benutzer auflisten", ("user", "list"), "z. B. --limit 100"),
            Command("Benutzer aus CSV importieren", (), "Geführter CSV-Import", True, "csv_import"),
            Command("Benutzer suchen", ("user", "search"), "SUCHTEXT"),
            Command("Benutzerdetails", ("user", "details"), "@name:server.tld"),
            Command("Benutzer ändern", ("user", "modify"), "@name:server.tld [OPTIONEN]"),
            Command("Passwort setzen", ("user", "password"), "@name:server.tld", True),
            Command("Benutzer deaktivieren", ("user", "deactivate"), "@name:server.tld", True),
            Command(
                "Benutzer löschen (GDPR)",
                ("user", "deactivate", "--gdpr-erase"),
                "@name:server.tld",
                True,
            ),
            Command("Raummitgliedschaften", ("user", "membership"), "@name:server.tld"),
            Command("Benutzer-Medien", ("user", "media"), "@name:server.tld [OPTIONEN]"),
            Command("Benutzer-Whois", ("user", "whois"), "@name:server.tld"),
        ),
    ),
    Section(
        "Moderation",
        (
            Command("Benutzer sperren", ("user", "suspend"), "@name:server.tld", True),
            Command("Benutzer entsperren", ("user", "suspend", "--unsuspend"), "@name:server.tld", True),
            Command("Shadow-Ban setzen", ("user", "shadow-ban"), "@name:server.tld", True),
            Command("Shadow-Ban aufheben", ("user", "shadow-ban", "--unban"), "@name:server.tld", True),
            Command("Alte Geräte prüfen", ("user", "prune-devices", "--list-only"), "@name:server.tld"),
            Command("Alte Geräte löschen", ("user", "prune-devices"), "@name:server.tld", True),
            Command("Nachrichten redigieren", ("user", "redact"), "@name:server.tld [OPTIONEN]", True),
            Command("Redaktionsstatus", ("user", "redact-status"), "VORGANGS-ID"),
        ),
    ),
    Section(
        "Räume",
        (
            Command("Raum anlegen", (), "Geführte Matrix-Raumerstellung", True, "create_room"),
            Command("Räume auflisten", ("room", "list"), "z. B. --limit 100"),
            Command("Raum suchen", ("room", "search"), "SUCHTEXT"),
            Command("Raum-Alias auflösen", ("room", "resolve"), "#alias:server.tld"),
            Command("Raumdetails", ("room", "details"), "!raumid:server.tld"),
            Command("Raummitglieder", ("room", "members"), "!raumid:server.tld"),
            Command("Benutzer Raum beitreten lassen", ("room", "join"), "RAUM BENUTZER", True),
            Command("Raumadministrator setzen", ("room", "make-admin"), "RAUM [BENUTZER]", True),
            Command("Raum-Berechtigungen", ("room", "power-levels"), "OPTIONEN"),
            Command("Raumstatus", ("room", "state"), "!raumid:server.tld"),
            Command("Blockierungsstatus", ("room", "block-status"), "!raumid:server.tld"),
            Command("Raum blockieren", ("room", "block"), "!raumid:server.tld", True),
            Command("Raum entsperren", ("room", "block", "--unblock"), "!raumid:server.tld", True),
            Command("Raum löschen", ("room", "delete"), "!raumid:server.tld [OPTIONEN]", True),
            Command("Raumlöschung prüfen", ("room", "delete-status", "--room-id"), "!raumid:server.tld"),
            Command("Leere Räume prüfen", ("room", "purge-empty", "--dry-run"), "OPTIONEN"),
            Command("Leere Räume löschen", ("room", "purge-empty"), "OPTIONEN", True),
        ),
    ),
    Section(
        "Medien",
        (
            Command("Medien auflisten", ("media", "list"), "OPTIONEN laut synadm media list -h"),
            Command("Medien quarantänisieren", ("media", "quarantine"), "OPTIONEN", True),
            Command("Quarantäne aufheben", ("media", "unquarantine"), "OPTIONEN"),
            Command("Medium schützen", ("media", "protect"), "MEDIEN-ID"),
            Command("Medium per ID löschen", ("media", "delete", "--media-id"), "MEDIEN-ID", True),
            Command("Medien löschen", ("media", "delete"), "OPTIONEN", True),
            Command("Remote-Medien bereinigen", ("media", "purge"), "OPTIONEN", True),
        ),
    ),
    Section(
        "Registrierung",
        (
            Command("Tokens auflisten", ("regtok", "list")),
            Command("Token anzeigen", ("regtok", "details"), "TOKEN"),
            Command("Token erstellen", ("regtok", "new"), "OPTIONEN"),
            Command("Token ändern", ("regtok", "update"), "TOKEN [OPTIONEN]"),
            Command("Token löschen", ("regtok", "delete"), "TOKEN", True),
        ),
    ),
    Section(
        "Weitere",
        (
            Command("Darstellung / Thema wählen", (), "Editionabhängige Farb- und Kontrastthemen", False, "choose_theme"),
            Command("Audit-Protokoll anzeigen", (), "Lokale, bereinigte Befehlschronik", False, "show_audit"),
            Command("synadm-Erstkonfiguration", (), "Geführte, sichere Einrichtung", False, "configure_synadm"),
            Command("synadm installieren/aktualisieren", (), "Installation mit pipx", True, "install_synadm"),
            Command("synadm deinstallieren", (), "Sauber aus pipx entfernen", True, "uninstall_synadm"),
            Command("pipx und synadm entfernen", (), "Paketumgebung bereinigen", True, "uninstall_pipx"),
            Command("Servernachricht senden", ("notice", "send"), "OPTIONEN"),
            Command("History-Purge", ("history", "purge"), "OPTIONEN", True),
            Command("History-Purge-Status", ("history", "purge-status"), "VORGANGS-ID"),
            Command("Eigener synadm-Befehl", (), "z. B. user list --limit 20"),
        ),
    ),
)
