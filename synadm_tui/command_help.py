"""Context help for catalogue commands."""

from __future__ import annotations

from dataclasses import dataclass

from .catalog import Command


@dataclass(frozen=True, slots=True)
class CommandInfo:
    description: str
    example: str
    writes: bool


DESCRIPTIONS = {
    "Serverversion": "Prüft die Verbindung und zeigt die Version des Synapse-Servers.",
    "synadm-Hilfe": "Zeigt die globale Hilfe und alle von synadm angebotenen Befehlsgruppen.",
    "Konfigurationshilfe": "Zeigt die offiziellen Optionen der synadm-Konfiguration.",
    "Benutzer auflisten": "Listet lokale Benutzer auf; Name und Anzahl können eingegrenzt werden.",
    "Benutzer aus CSV importieren": "Legt mehrere Benutzer anhand einer CSV-Datei kontrolliert an oder ändert sie.",
    "Benutzer suchen": "Sucht Benutzer nach Matrix-ID, lokalem Namen oder Anzeigenamen.",
    "Benutzerdetails": "Zeigt Kontodaten und Status eines einzelnen Benutzers.",
    "Benutzer ändern": "Ändert Profil-, Kontakt- oder administrative Eigenschaften eines Benutzers.",
    "Passwort setzen": "Setzt ein neues Passwort für ein lokales Benutzerkonto.",
    "Benutzer deaktivieren": "Deaktiviert ein Benutzerkonto; je nach Optionen können Daten gelöscht werden.",
    "Benutzer-Whois": "Zeigt Geräte, Sitzungen und IP-Informationen eines Benutzers.",
    "Räume auflisten": "Listet Räume des Homeservers mit optionalem Filter auf.",
    "Raum suchen": "Sucht Räume anhand von Name, Alias oder ID.",
    "Raumdetails": "Zeigt Metadaten und administrative Informationen eines Raums.",
    "Raummitglieder": "Listet die Mitglieder eines Raums auf.",
    "Raumstatus": "Liest den aktuellen Matrix-Zustand eines Raums.",
    "Raum blockieren": "Ändert den administrativen Blockierungsstatus eines Raums.",
    "Raum löschen": "Entfernt einen Raum administrativ und kann Mitglieder entfernen.",
    "Medien auflisten": "Listet lokale oder entfernte Medien anhand der synadm-Optionen auf.",
    "Medien quarantänisieren": "Sperrt ausgewählte Medien für die weitere Auslieferung.",
    "Quarantäne aufheben": "Gibt zuvor quarantänisierte Medien wieder frei.",
    "Medien löschen": "Löscht ausgewählte Mediendateien vom Homeserver.",
    "Remote-Medien bereinigen": "Bereinigt zwischengespeicherte Medien anderer Homeserver.",
    "Tokens auflisten": "Listet Registrierungstokens und deren Status auf.",
    "Token anzeigen": "Zeigt Details und Nutzungslimits eines Registrierungstokens.",
    "Token erstellen": "Erzeugt ein neues Registrierungstoken.",
    "Token ändern": "Ändert Gültigkeit oder Nutzungslimits eines Registrierungstokens.",
    "Token löschen": "Löscht ein Registrierungstoken.",
    "Darstellung / Thema wählen": "Wechselt Farbschema und Startgrafik der aktuellen Edition.",
    "synadm-Erstkonfiguration": "Erstellt oder ersetzt eine geschützte synadm-Konfiguration und testet sie.",
    "synadm installieren/aktualisieren": "Installiert beziehungsweise aktualisiert synadm isoliert über pipx.",
    "synadm deinstallieren": "Entfernt die von pipx verwaltete synadm-Installation.",
    "pipx und synadm entfernen": "Entfernt synadm und anschließend pipx, sofern keine anderen Apps betroffen sind.",
    "Servernachricht senden": "Sendet eine administrative Servernachricht an Benutzer.",
    "History-Purge": "Löscht historische Ereignisse eines Raums bis zu einem gewählten Zeitpunkt.",
    "Eigener synadm-Befehl": "Führt einen frei angegebenen synadm-Unterbefehl ohne Shell-Auswertung aus.",
}

EXAMPLES = {
    "Benutzer aus CSV importieren": "CSV-Datei wählen → Spalten zuordnen → Vorschau bestätigen",
    "Benutzer suchen": "synadm user search alice --limit 20",
    "Benutzerdetails": "synadm user details @alice:example.org",
    "Benutzer ändern": "synadm user modify @alice:example.org --display-name Alice",
    "Passwort setzen": "synadm user password @alice:example.org",
    "Räume auflisten": "synadm room list --limit 50",
    "Raumdetails": "synadm room details '!raumid:example.org'",
    "Raum blockieren": "synadm room block '!raumid:example.org'",
    "Token anzeigen": "synadm regtok details EINLADUNG2026",
    "Eigener synadm-Befehl": "user list --limit 20",
    "synadm-Erstkonfiguration": "c drücken und den neun Schritten folgen",
    "Darstellung / Thema wählen": "t drücken, Thema auswählen, Enter",
}

WRITE_TITLES = {
    "Benutzer aus CSV importieren", "Benutzer ändern", "Passwort setzen",
    "Benutzer deaktivieren", "Raum blockieren", "Raum löschen",
    "Medien quarantänisieren", "Quarantäne aufheben", "Medien löschen",
    "Remote-Medien bereinigen", "Token erstellen", "Token ändern",
    "Token löschen", "synadm-Erstkonfiguration", "synadm installieren/aktualisieren",
    "synadm deinstallieren", "pipx und synadm entfernen", "Servernachricht senden",
    "History-Purge", "Eigener synadm-Befehl",
}


def command_info(command: Command) -> CommandInfo:
    if command.title in EXAMPLES:
        example = EXAMPLES[command.title]
    elif command.argv:
        suffix = f" {command.hint}" if command.hint else ""
        example = "synadm " + " ".join(command.argv) + suffix
    else:
        example = command.hint or "Über das Auswahlmenü starten"
    return CommandInfo(
        DESCRIPTIONS.get(command.title, f"Führt die Funktion „{command.title}“ über synadm aus."),
        example,
        command.title in WRITE_TITLES or command.dangerous,
    )
