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
            Command("Benutzer-Whois", ("user", "whois"), "@name:server.tld"),
        ),
    ),
    Section(
        "Räume",
        (
            Command("Räume auflisten", ("room", "list"), "z. B. --limit 100"),
            Command("Raum suchen", ("room", "search"), "SUCHTEXT"),
            Command("Raumdetails", ("room", "details"), "!raumid:server.tld"),
            Command("Raummitglieder", ("room", "members"), "!raumid:server.tld"),
            Command("Raumstatus", ("room", "state"), "!raumid:server.tld"),
            Command("Raum blockieren", ("room", "block"), "!raumid:server.tld", True),
            Command("Raum löschen", ("room", "delete"), "!raumid:server.tld [OPTIONEN]", True),
        ),
    ),
    Section(
        "Medien",
        (
            Command("Medien auflisten", ("media", "list"), "OPTIONEN laut synadm media list -h"),
            Command("Medien quarantänisieren", ("media", "quarantine"), "OPTIONEN", True),
            Command("Quarantäne aufheben", ("media", "unquarantine"), "OPTIONEN"),
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
            Command("synadm-Erstkonfiguration", (), "Geführte, sichere Einrichtung", False, "configure_synadm"),
            Command("synadm installieren/aktualisieren", (), "Installation mit pipx", True, "install_synadm"),
            Command("synadm deinstallieren", (), "Sauber aus pipx entfernen", True, "uninstall_synadm"),
            Command("pipx und synadm entfernen", (), "Paketumgebung bereinigen", True, "uninstall_pipx"),
            Command("Servernachricht senden", ("notice", "send"), "OPTIONEN"),
            Command("History-Purge", ("history", "purge"), "OPTIONEN", True),
            Command("Eigener synadm-Befehl", (), "z. B. user list --limit 20"),
        ),
    ),
)
