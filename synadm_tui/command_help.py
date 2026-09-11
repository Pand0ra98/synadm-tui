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
    "Benutzer anlegen": (
        "Legt ein lokales Matrix-Benutzerkonto mit Passwort, Anzeigename, E-Mail "
        "und optionalen Eigenschaften kontrolliert an."
    ),
    "Benutzer aus CSV importieren": "Legt mehrere Benutzer anhand einer CSV-Datei kontrolliert an oder ändert sie.",
    "Benutzer suchen": "Sucht Benutzer nach Matrix-ID, lokalem Namen oder Anzeigenamen.",
    "Benutzerdetails": "Zeigt Kontodaten und Status eines einzelnen Benutzers.",
    "Benutzer ändern": "Ändert Profil-, Kontakt- oder administrative Eigenschaften eines Benutzers.",
    "Passwort setzen": "Setzt ein neues Passwort für ein lokales Benutzerkonto.",
    "Benutzer deaktivieren": "Deaktiviert ein Benutzerkonto; je nach Optionen können Daten gelöscht werden.",
    "Benutzer löschen (GDPR)": (
        "Deaktiviert das Konto dauerhaft und markiert es über Synapse als GDPR-gelöscht. "
        "Sitzungen, Passwort und Drittanbieter-IDs werden entfernt; der Datenbankeintrag selbst bleibt bestehen."
    ),
    "Benutzer-Whois": "Zeigt Geräte, Sitzungen und IP-Informationen eines Benutzers.",
    "Raummitgliedschaften": "Listet alle Räume auf, in denen ein Benutzer Mitglied ist.",
    "Benutzer-Medien": "Listet die von einem Benutzer hochgeladenen lokalen Medien auf.",
    "Benutzer sperren": "Friert ein Konto ein, ohne es zu deaktivieren oder zu löschen.",
    "Benutzer entsperren": "Hebt eine zuvor gesetzte Kontosperre wieder auf.",
    "Shadow-Ban setzen": "Schränkt ein missbräuchliches Konto unauffällig ein; nur als letztes Mittel verwenden.",
    "Shadow-Ban aufheben": "Entfernt den Shadow-Ban eines Benutzerkontos.",
    "Alte Geräte prüfen": "Zeigt im Dry-Run, welche alten Geräte und Sitzungen entfernt würden.",
    "Alte Geräte löschen": "Entfernt ausgewählte alte Geräte und macht deren Zugriffstoken ungültig.",
    "Nachrichten redigieren": "Startet die Redaktion von Ereignissen eines Benutzers, optional auf Räume begrenzt.",
    "Redaktionsstatus": "Zeigt den Fortschritt einer zuvor gestarteten Nachrichtenredaktion.",
    "Raum anlegen": (
        "Erstellt über die Matrix-Client-API einen Raum. Der konfigurierte Admin-Benutzer "
        "wird Ersteller; Token und Verbindung stammen geschützt aus der synadm-Konfiguration."
    ),
    "Räume auflisten": "Listet Räume des Homeservers mit optionalem Filter auf.",
    "Raum suchen": "Sucht Räume anhand von Name, Alias oder ID.",
    "Raum-Alias auflösen": "Ermittelt zu einem Alias die Raum-ID oder mit Zusatzoptionen die Aliase einer Raum-ID.",
    "Raumdetails": "Zeigt Metadaten und administrative Informationen eines Raums.",
    "Raummitglieder": "Listet die Mitglieder eines Raums auf.",
    "Benutzer Raum beitreten lassen": "Lässt einen Benutzer administrativ einem Raum beitreten.",
    "Raumadministrator setzen": "Erteilt dem gewählten Benutzer administrative Rechte im Raum.",
    "Raum-Berechtigungen": "Zeigt Power-Level und Berechtigungen eines oder mehrerer Räume.",
    "Raumstatus": "Liest den aktuellen Matrix-Zustand eines Raums.",
    "Raum blockieren": "Ändert den administrativen Blockierungsstatus eines Raums.",
    "Raum entsperren": "Hebt die administrative Blockierung eines Raums auf.",
    "Blockierungsstatus": "Zeigt, ob und durch wen ein Raum blockiert wurde.",
    "Raum löschen": "Entfernt einen Raum administrativ und kann Mitglieder entfernen.",
    "Raumlöschung prüfen": "Zeigt den Fortschritt der asynchronen Löschung eines Raums.",
    "Leere Räume prüfen": "Listet per Dry-Run Räume ohne lokale Mitglieder auf.",
    "Leere Räume löschen": "Löscht Räume ohne lokale Mitglieder nach einer Sicherheitsbestätigung.",
    "Medien auflisten": "Listet lokale oder entfernte Medien anhand der synadm-Optionen auf.",
    "Medien quarantänisieren": "Sperrt ausgewählte Medien für die weitere Auslieferung.",
    "Quarantäne aufheben": "Gibt zuvor quarantänisierte Medien wieder frei.",
    "Medium schützen": "Markiert ein lokales Medium als vor automatischer Bereinigung geschützt.",
    "Medium per ID löschen": "Löscht genau ein lokales Medium anhand seiner Medien-ID.",
    "Medien löschen": "Löscht ausgewählte Mediendateien vom Homeserver.",
    "Remote-Medien bereinigen": "Bereinigt zwischengespeicherte Medien anderer Homeserver.",
    "Tokens auflisten": "Listet Registrierungstokens und deren Status auf.",
    "Token anzeigen": "Zeigt Details und Nutzungslimits eines Registrierungstokens.",
    "Token erstellen": "Erzeugt ein neues Registrierungstoken.",
    "Token ändern": "Ändert Gültigkeit oder Nutzungslimits eines Registrierungstokens.",
    "Token löschen": "Löscht ein Registrierungstoken.",
    "Darstellung / Thema wählen": "Wechselt Farbschema und Startgrafik der aktuellen Edition.",
    "Audit-Protokoll anzeigen": "Zeigt die lokale Befehlschronik; Passwörter und Tokens werden nicht gespeichert.",
    "Demo-Modus umschalten": "Wechselt im laufenden Programm zwischen echter synadm-Verbindung und lokalem Demo-Backend.",
    "synadm-Erstkonfiguration": "Erstellt oder ersetzt eine geschützte synadm-Konfiguration und testet sie.",
    "synadm installieren/aktualisieren": "Installiert beziehungsweise aktualisiert synadm isoliert über pipx.",
    "synadm deinstallieren": "Entfernt die von pipx verwaltete synadm-Installation.",
    "pipx und synadm entfernen": "Entfernt synadm und anschließend pipx, sofern keine anderen Apps betroffen sind.",
    "Servernachricht senden": "Sendet eine administrative Servernachricht an Benutzer.",
    "History-Purge": "Löscht historische Ereignisse eines Raums bis zu einem gewählten Zeitpunkt.",
    "History-Purge-Status": "Zeigt den Fortschritt einer laufenden History-Bereinigung.",
    "Eigener synadm-Befehl": "Führt einen frei angegebenen synadm-Unterbefehl ohne Shell-Auswertung aus.",
}

EXAMPLES = {
    "Benutzer anlegen": "Assistent → Matrix-ID, Passwort, Anzeigename, E-Mail und Rollenoptionen prüfen",
    "Benutzer aus CSV importieren": "CSV-Datei wählen → Spalten zuordnen → Vorschau bestätigen",
    "Benutzer suchen": "synadm user search alice --limit 20",
    "Benutzerdetails": "synadm user details @alice:example.org",
    "Benutzer ändern": "synadm user modify @alice:example.org --display-name Alice",
    "Passwort setzen": "synadm user password @alice:example.org",
    "Benutzer löschen (GDPR)": "synadm user deactivate --gdpr-erase @alice:example.org",
    "Raummitgliedschaften": "synadm user membership @alice:example.org",
    "Benutzer-Medien": "synadm user media @alice:example.org --limit 50",
    "Benutzer sperren": "synadm user suspend @alice:example.org",
    "Benutzer entsperren": "synadm user suspend --unsuspend @alice:example.org",
    "Shadow-Ban setzen": "synadm user shadow-ban @alice:example.org",
    "Alte Geräte prüfen": "synadm user prune-devices --list-only @alice:example.org --min-days 90",
    "Alte Geräte löschen": "synadm user prune-devices @alice:example.org --min-days 90",
    "Nachrichten redigieren": "synadm user redact @alice:example.org --room '!raum:example.org'",
    "Raum anlegen": "Assistent → Name, Alias, Sichtbarkeit, Vorlage, Einladungen und Föderation prüfen",
    "Räume auflisten": "synadm room list --limit 50",
    "Raumdetails": "synadm room details '!raumid:example.org'",
    "Raum-Alias auflösen": "synadm room resolve '#projekt:example.org'",
    "Benutzer Raum beitreten lassen": "synadm room join '!raum:example.org' @alice:example.org",
    "Raumadministrator setzen": "synadm room make-admin '!raum:example.org' --user-id @alice:example.org",
    "Raum blockieren": "synadm room block '!raumid:example.org'",
    "Raum entsperren": "synadm room block --unblock '!raumid:example.org'",
    "Blockierungsstatus": "synadm room block-status '!raumid:example.org'",
    "Raumlöschung prüfen": "synadm room delete-status --room-id '!raumid:example.org'",
    "Leere Räume prüfen": "synadm room purge-empty --dry-run",
    "Medium per ID löschen": "synadm media delete --media-id abcdef123456",
    "Token anzeigen": "synadm regtok details EINLADUNG2026",
    "Eigener synadm-Befehl": "user list --limit 20",
    "synadm-Erstkonfiguration": "c drücken und den neun Schritten folgen",
    "Darstellung / Thema wählen": "t drücken, Thema auswählen, Enter",
    "Audit-Protokoll anzeigen": "~/.local/state/synadm-tui/audit.jsonl",
    "Demo-Modus umschalten": "d drücken oder diesen Menüpunkt öffnen",
}

WRITE_TITLES = {
    "Benutzer anlegen", "Benutzer aus CSV importieren", "Benutzer ändern", "Passwort setzen", "Medium schützen",
    "Benutzer deaktivieren", "Benutzer löschen (GDPR)", "Raum anlegen", "Raum blockieren", "Raum löschen",
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
