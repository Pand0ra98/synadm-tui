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
- neutrale **Standard Edition** ohne regionale Branding-Ressourcen
- umschaltbare Themen **Retro Cyberspace 198X**, **Matrix**, **Hacker Terminal**, **Hoher Kontrast** und **Monochrom**
- transparente PNG-Embleme für Retro Cyberspace und Hacker Terminal in Kitty-, WezTerm- und Ghostty-kompatiblen Terminals
- farbiger Unicode-Halbblock-Renderer für Alacritty, Zellij und andere 256-Farben-Terminals; Text-Fallback für stark eingeschränkte Terminals
- kräftige Doppelrahmen, thematische Startgrafiken und zentrierte Paneltitel
- nicht blockierende Ausführung; die Oberfläche bleibt während eines API-Aufrufs bedienbar
- formatierte JSON-Ausgabe mit Scrollfunktion
- zusätzliche Bestätigung vor als destruktiv markierten Befehlen
- sichere Prozessaufrufe als Argumentliste, ohne Shell-Auswertung
- geführte Eingabeassistenten für Suche, IDs, Limits und Benutzeränderungen
- Rückwärtsnavigation mit `Shift+Tab` in mehrstufigen Assistenten
- globaler Befehlsfilter, Tastaturhilfe und Detailtexte mit Beispielen
- alternative `synadm`-Binärdatei und Konfiguration per Startoption
- geführte Installation beziehungsweise Aktualisierung von `synadm` über `pipx`
- sicherer Erstkonfigurations-Assistent für Server, Admin-Zugriffstoken und API-Einstellungen
- geführter CSV-Import mit Trennzeichenerkennung, Spaltenzuordnung und Vorschau
- nur Python-Standardbibliothek; keine Laufzeitabhängigkeiten

## Voraussetzungen

- Python 3.10 oder neuer auf Linux/macOS
- UTF-8-Terminal; für eingeschränkte Darstellung stehen Kontrast- und Monochromthemen bereit
- `synadm`, wahlweise bereits installiert oder über die TUI nachinstalliert
- ein Admin-Zugriffstoken in der `synadm`-Konfiguration

`synadm` selbst lässt sich üblicherweise mit `pipx install synadm` installieren. Vor dem ersten TUI-Start sollte `synadm version` im selben Benutzerkonto funktionieren.

`synadm` kann direkt unter **Weitere → synadm installieren/aktualisieren** nachinstalliert oder aktualisiert werden. Fehlt `pipx`, fragt die TUI, ob es zunächst benutzerlokal über Python/pip installiert werden soll. Jeder Befehl wird vorher angezeigt und verlangt eine ausdrückliche Bestätigung.

Unter **Weitere** stehen außerdem getrennte Aktionen zum Entfernen von `synadm` sowie zum vollständigen Entfernen von `synadm` und `pipx` bereit. `pipx` wird nicht automatisch entfernt, solange es noch andere Anwendungen verwaltet. Bei einer systemweiten Installation verwendet die TUI den erkannten Paketmanager; ohne Root-Rechte funktioniert dies nur mit einer bereits autorisierten passwortlosen `sudo`-Sitzung.

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
./dist/synadm-tui.pyz --version
./dist/synadm-tui.pyz
```

Die erzeugte Datei `dist/synadm-tui.pyz` enthält den gesamten Anwendungscode und kann direkt kopiert werden. Auf dem Zielsystem werden weiterhin Python 3.10+ sowie das separat installierte Programm `synadm` benötigt.

Für eine vollständig native Datei, die kein installiertes Python benötigt:

```bash
python3 -m pip install pyinstaller
python3 scripts/build_native.py
./dist/synadm-tui --version
cd dist
sha256sum --check SHA256SUMS
```

Der Build erzeugt die neutrale Standard Edition und die Prüfsummendatei `SHA256SUMS`.

PyInstaller ist bewusst nur eine Build- und keine Laufzeitabhängigkeit. Die nativen Dateien werden für das Betriebssystem und die Prozessorarchitektur des Build-Rechners erstellt. `synadm` selbst bleibt ein separates Programm, kann aber aus der TUI heraus installiert werden.

## DEB- und RPM-Pakete ohne Runner

Aus den beiden nativen Dateien lassen sich lokal installierbare Pakete erzeugen. Benötigt werden `dpkg-deb` für Debian-Pakete und `rpmbuild` aus dem Paket `rpm` beziehungsweise `rpm-build` für RPM-Pakete:

```bash
python3 scripts/build_native.py
python3 scripts/build_packages.py
cd dist/packages
sha256sum --check SHA256SUMS
```

Das Ergebnis enthält jeweils ein DEB- und RPM-Paket. Die Build-Architektur wird automatisch auf `amd64`/`x86_64` beziehungsweise `arm64`/`aarch64` abgebildet. Das Skript verweigert die Paketierung, wenn die Versionsnummer der nativen Datei nicht zu `pyproject.toml` passt.

Die aktuellen Linux-Dateien benötigen mindestens glibc 2.34. Für eine möglichst breite Kompatibilität sollten Release-Dateien später in einer festgelegten, älteren Build-Umgebung erzeugt werden.

### Manuell in Gitea veröffentlichen

Der Zugriffstoken benötigt den Gitea-Scope `write:package`. Er wird ausschließlich aus der Umgebungsvariable gelesen und nicht als Prozessargument übergeben:

```bash
read -rsp "Gitea-Paket-Token: " GITEA_PACKAGE_TOKEN
export GITEA_PACKAGE_TOKEN
python3 scripts/publish_packages.py --dry-run
python3 scripts/publish_packages.py
unset GITEA_PACKAGE_TOKEN
```

Wenn bereits ein entsprechend berechtigter `tea`-Login vorhanden ist, kann dessen Token ohne erneute Eingabe und ohne Ausgabe gelesen werden:

```bash
python3 scripts/publish_packages.py --tea-login Building
```

Standardmäßig werden die Pakete unter dem Eigentümer `pan`, DEB-Distribution `stable`, Komponente `main` und der gruppenlosen RPM-Registry veröffentlicht. Server, Eigentümer und Repository-Gruppen lassen sich über die Kommandozeilenoptionen anpassen. Dafür ist kein Actions-Runner erforderlich.

### Paketquelle verwenden

Debian und Ubuntu:

```bash
sudo install -d -m 0755 /etc/apt/keyrings
sudo curl -fsSL https://git.blackwall.ipv64.de/api/packages/pan/debian/repository.key \
  -o /etc/apt/keyrings/pan-gitea.asc
echo "deb [signed-by=/etc/apt/keyrings/pan-gitea.asc] https://git.blackwall.ipv64.de/api/packages/pan/debian stable main" \
  | sudo tee /etc/apt/sources.list.d/synadm-tui.list
sudo apt update
sudo apt install synadm-tui
```

Fedora, RHEL und kompatible Systeme:

```bash
sudo curl -fsSL https://git.blackwall.ipv64.de/api/packages/pan/rpm.repo \
  -o /etc/yum.repos.d/synadm-tui.repo
sudo dnf install synadm-tui
```

Die separat gepflegte [Thüringen Edition](https://git.blackwall.ipv64.de/pan/synadm-tui-thueringen) verwendet denselben Anwendungskern, bringt ihr Branding und ihre Pakete aber in einem eigenen Repository mit.

## Bedienung

| Taste | Funktion |
|---|---|
| `↑` / `↓`, `k` / `j` | In der aktiven Spalte auswählen |
| `Enter` | Bereich bestätigen beziehungsweise Befehl ausführen |
| `←`, `Esc`, `h` | Von den Befehlen zurück zur Bereichsauswahl |
| `n` | Benutzer anlegen |
| `i` | CSV-Import öffnen |
| `/` | Benutzer suchen |
| `c` | synadm-Konfigurationsassistent öffnen |
| `f` | Befehle über alle Bereiche filtern |
| `?` | Tastaturhilfe anzeigen |
| `t` | Themenauswahl öffnen |
| `Shift+Tab` | Im Assistenten einen Schritt zurückgehen |
| `PgUp` / `PgDn`, `Home` | Ausgabe scrollen |
| `r` | letzten Befehl wiederholen |
| `q` | beenden |
| `Esc` | Eingabe oder Bestätigung abbrechen |

Geführte Assistenten fragen häufige Werte wie Suchtext, Limit und Matrix-ID einzeln ab. Mit `Shift+Tab` geht es zum vorherigen Schritt; `Backspace` tut dies ebenfalls, wenn das aktuelle Eingabefeld bereits leer ist. Erweiterte Argumente werden wie in der Shell geschrieben; Anführungszeichen werden unterstützt. Die Eingabe wird mit `shlex` zerlegt und **nicht** durch eine Shell ausgeführt. Die Reaktionszeit der einzelnen `Esc`-Taste wird auf 35 ms reduziert.

`·` kennzeichnet lesende, `+` schreibende und `!` besonders gefährliche Aktionen. Der Detailbereich erklärt die Auswahl und zeigt ein Beispiel. Für gefährliche Aktionen verlangt die TUI eine zweite Bestätigung. Trotzdem empfiehlt sich vor großflächigen Verwaltungsaktionen ein aktuelles Synapse-Backup.

Die Erstkonfiguration ist mit `c` sowie unter **Weitere → synadm-Erstkonfiguration** erreichbar. Der Assistent fragt Konfigurationspfad, Admin-Benutzer, Zugriffstoken, Verbindung, API-Pfade, Homeserver-Erkennung, Ausgabeformat, Timeout und TLS-Prüfung ab. Vorhandene Dateien werden vor dem Überschreiben als zeitgestempelte `.bak-*`-Datei gesichert. Das Ergebnis wird atomar mit Dateirechten `0600` gespeichert; ein anschließender Diagnoseaufruf zeigt Erfolg oder Fehlergrund im Detailbereich.

Alternativ bleibt die interaktive Einrichtung von `synadm` auf der Kommandozeile möglich:

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

Die Themenauswahl ist jederzeit mit `t` sowie unter **Weitere → Darstellung / Thema wählen** erreichbar. Mit `↑`/`↓` wird die Farbgebung live ausprobiert, `Enter` speichert sie editionsabhängig unter `~/.config/synadm-tui/`, und `Esc` stellt das vorherige Thema wieder her.

Die Standard Edition enthält die generierten Embleme `retro-cyberspace.png` und `hacker-terminal.png`. Unterstützt das Terminal das Kitty-Grafikprotokoll – beispielsweise Kitty, WezTerm oder Ghostty –, erscheint das zum aktiven Thema passende transparente PNG direkt im Detailbereich. Unter Alacritty, innerhalb von Zellij und in anderen 256-Farben-Terminals zeichnet die TUI automatisch eine kompakte farbige Annäherung mit Unicode-Halbblöcken. Nur wenn auch das nicht möglich ist, wird die reine Textgrafik verwendet. Sixel wird dafür nicht benötigt.

## Sicherheit

- `synadm-tui` startet Prozesse ohne Shell und aktiviert den nicht-interaktiven `synadm`-Modus.
- Der Erstkonfigurations-Assistent schreibt den eingegebenen Zugriffstoken ausschließlich in die gewählte `synadm`-Konfigurationsdatei. Er wird verdeckt eingegeben, nicht in der Vorschau angezeigt und nicht als Prozessargument übergeben.
- Neu erzeugte Konfigurationsdateien werden atomar geschrieben und erhalten auf POSIX-Systemen die Dateirechte `0600`.
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
| `command_help.py` | Beschreibungen, Beispiele und Schreibschutz-Kennzeichnung |
| `configuration.py` | Validierung, Sicherung und atomare synadm-Konfiguration |
| `edition.py` | neutrales Standardprofil und Erweiterungsschnittstelle für externe Editionen |
| `terminal_image.py` | optionale transparente PNG-Darstellung über das Kitty-Grafikprotokoll |
| `block_art.py` | protokollfreie 256-Farben-Darstellung für Alacritty und Multiplexer |
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
