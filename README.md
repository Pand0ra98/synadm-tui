# synadm TUI

Eine tastaturorientierte Terminal-Oberfläche für [`synadm`](https://synadm.readthedocs.io/), das Admin-CLI für Matrix Synapse. Das LazyDocker-inspirierte Panel-Layout bündelt Benutzer, Räume, Medien und Registrierung, ohne den Zugriff auf beliebige `synadm`-Befehle einzuschränken.

> **Projektstatus:** frühe, funktionsfähige Version. Vor produktiven Massenänderungen immer Synapse-Backups und eine Testumgebung verwenden.

## Schnellstart

```bash
git clone <REPOSITORY-URL> synadm-tui
cd synadm-tui
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
synadm-tui
```

Für einen Start ohne Installation:

```bash
python3 -m synadm_tui
```

## Eigenschaften

- übersichtliche Drei-Spalten-Navigation ohne Maus
- nicht blockierende Ausführung; die Oberfläche bleibt während eines API-Aufrufs bedienbar
- formatierte JSON-Ausgabe mit Scrollfunktion
- zusätzliche Bestätigung vor als destruktiv markierten Befehlen
- sichere Prozessaufrufe als Argumentliste, ohne Shell-Auswertung
- geführte Eingabeassistenten für Suche, IDs, Limits und Benutzeränderungen
- alternative `synadm`-Binärdatei und Konfiguration per Startoption
- geführter CSV-Import mit Trennzeichenerkennung, Spaltenzuordnung und Vorschau
- nur Python-Standardbibliothek; keine Laufzeitabhängigkeiten

## Voraussetzungen

- Python 3.10 oder neuer auf Linux/macOS
- installiertes und konfiguriertes `synadm`
- ein Admin-Zugriffstoken in der `synadm`-Konfiguration

`synadm` selbst lässt sich üblicherweise mit `pipx install synadm` installieren. Vor dem ersten TUI-Start sollte `synadm version` im selben Benutzerkonto funktionieren.

## Installation

Aus diesem Verzeichnis:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install .
synadm-tui
```

Alternative Programm- oder Konfigurationspfade:

```bash
synadm-tui --synadm /opt/synadm/bin/synadm \
  --config-file ~/.config/synadm.yaml --timeout 90
```

## Einzelne ausführbare Datei bauen

Ohne zusätzliche Build-Abhängigkeiten kann eine einzelne ausführbare Datei erzeugt werden:

```bash
python3 scripts/build_executable.py
./dist/synadm-tui --version
./dist/synadm-tui
```

Die erzeugte Datei `dist/synadm-tui` enthält den gesamten Anwendungscode und kann direkt kopiert werden. Auf dem Zielsystem werden weiterhin Python 3.10+ sowie das separat installierte Programm `synadm` benötigt.

Für eine vollständig native Datei, die kein installiertes Python benötigt:

```bash
python3 -m pip install pyinstaller
python3 scripts/build_native.py
./dist/synadm-tui-native --version
```

PyInstaller ist bewusst nur eine Build- und keine Laufzeitabhängigkeit. Die native Datei wird für das Betriebssystem und die Prozessorarchitektur des Build-Rechners erstellt. `synadm` selbst muss weiterhin separat installiert und konfiguriert sein.

## Bedienung

| Taste | Funktion |
|---|---|
| `↑` / `↓`, `k` / `j` | In der aktiven Spalte auswählen |
| `Enter` | Bereich bestätigen beziehungsweise Befehl ausführen |
| `←`, `Esc`, `h` | Von den Befehlen zurück zur Bereichsauswahl |
| `n` | Benutzer anlegen |
| `i` | CSV-Import öffnen |
| `/` | Benutzer suchen |
| `PgUp` / `PgDn`, `Home` | Ausgabe scrollen |
| `r` | letzten Befehl wiederholen |
| `q` | beenden |
| `Esc` | Eingabe oder Bestätigung abbrechen |

Geführte Assistenten fragen häufige Werte wie Suchtext, Limit und Matrix-ID einzeln ab. Erweiterte Argumente werden wie in der Shell geschrieben; Anführungszeichen werden unterstützt. Die Eingabe wird mit `shlex` zerlegt und **nicht** durch eine Shell ausgeführt.

Gelb und mit `!` markierte Einträge verändern oder löschen Daten. Die TUI verlangt dafür eine zweite Bestätigung. Trotzdem empfiehlt sich vor großflächigen Verwaltungsaktionen ein aktuelles Synapse-Backup.

Interaktive Zugangsdaten gehören nicht in die Kommandozeile. Login und Erstkonfiguration daher außerhalb der TUI ausführen:

```bash
synadm config
synadm matrix login @admin:example.org
```

## Benutzer aus CSV importieren

Unter **Benutzer → Benutzer aus CSV importieren** führt ein Assistent durch vier Schritte:

1. UTF-8-CSV-Datei im eingebauten Dateibrowser auswählen
2. automatisch erkanntes Trennzeichen in einem Auswahlmenü prüfen oder ändern und Kopfzeile angeben
3. CSV-Spalten mit `←`/`→` den Zielfeldern zuordnen; eine Tabelle zeigt dabei Kopfzeile und erste Datensätze
4. Benutzer-Vorschau prüfen und Import bestätigen

Unterstützte Zielfelder sind Benutzer-ID, Passwort, Anzeigename, E-Mail, Adminstatus, Benutzertyp, Avatar-URL und Sperrstatus. Nur die Benutzer-ID ist verpflichtend; zusätzlich muss mindestens ein anzulegender Wert vorhanden sein. Wahrheitswerte akzeptieren unter anderem `ja`/`nein`, `true`/`false` und `1`/`0`. Zulässige Benutzertypen sind `regular`, `bot` und `support`.

Beispiel:

```csv
username;password;display_name;email;admin;type
@alice:example.org;Start-123;Alice;alice@example.org;nein;regular
@service:example.org;Bot-456;Service Bot;;nein;bot
```

Der Assistent blendet Passwörter in Vorschau und Ergebnis aus. Da `synadm` im nicht-interaktiven Modus Passwörter über `--password` entgegennimmt, können sie während des kurzen Unterprozesses für andere Prozesse desselben Systems sichtbar sein. CSV-Datei und Host sollten entsprechend geschützt werden; Startpasswörter anschließend wechseln lassen.

Im Dateibrowser öffnet `Enter` ein Verzeichnis beziehungsweise wählt eine CSV-Datei aus. `←` oder `Backspace` wechselt zum Elternverzeichnis. Mit `p` kann weiterhin ein Pfad direkt eingegeben werden.

In Ja/Nein-Dialogen wird die gewünschte Schaltfläche mit `←`/`→` gewählt und mit `Enter` bestätigt. Sicherheitsabfragen starten grundsätzlich auf **Nein**.

## Sicherheit

- `synadm-tui` startet Prozesse ohne Shell und aktiviert den nicht-interaktiven `synadm`-Modus.
- Zugriffstokens werden weder gelesen noch von der TUI gespeichert; hierfür bleibt `synadm` zuständig.
- Passwörter werden in Eingabe, Vorschau und Ergebnis maskiert.
- Beim nicht-interaktiven Benutzerimport muss `synadm` Passwörter kurzzeitig als Prozessargument erhalten. Auf Mehrbenutzersystemen können andere privilegierte Prozesse diese möglicherweise sehen.
- Konfigurationsdateien, `.env`-Dateien und lokale YAML-Konfigurationen sind standardmäßig von Git ausgeschlossen.

## Architektur

| Modul | Aufgabe |
|---|---|
| `app.py` | curses-Oberfläche, Navigation und Assistenten |
| `runner.py` | sichere `synadm`-Prozessausführung |
| `catalog.py` | Bereiche und verfügbare Aktionen |
| `assistants.py` | strukturierte Eingabefelder pro Befehl |
| `csv_import.py` | CSV-Erkennung, Validierung und Importplanung |
| `file_browser.py` | Dateibrowser für CSV-Dateien |

## Entwicklung

```bash
python3 -m unittest discover -v
python3 -m compileall -q synadm_tui
python3 scripts/build_executable.py
```

Die Tests verwenden ausschließlich die Standardbibliothek und benötigen keinen erreichbaren Synapse-Server. Weitere Hinweise stehen in [CONTRIBUTING.md](CONTRIBUTING.md).

## Lizenz

GPL-3.0-or-later, siehe [LICENSE](LICENSE).
