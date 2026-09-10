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

- übersichtliche Drei-Spalten-Navigation mit Tastatur- und Maussteuerung
- neutrale **Standard Edition** ohne regionale Branding-Ressourcen
- **Thüringen Edition** mit eigenem Branding und identischem Anwendungskern
- umschaltbare Themen **Retro Cyberspace 198X**, **Matrix**, **Hacker Terminal**, **Hoher Kontrast** und **Monochrom**
- transparente PNG-Embleme für Retro Cyberspace und Hacker Terminal in Kitty-, WezTerm- und Ghostty-kompatiblen Terminals
- farbiger Unicode-Halbblock-Renderer für Alacritty, Zellij und andere 256-Farben-Terminals; Text-Fallback für stark eingeschränkte Terminals
- kräftige Doppelrahmen, thematische Startgrafiken und zentrierte Paneltitel
- nicht blockierende Ausführung; die Oberfläche bleibt während eines API-Aufrufs bedienbar
- filter- und sortierbare Tabellenansicht für Benutzer, Räume, Geräte und Medien
- zusätzliche Bestätigung sowie exakte Zieleingabe vor besonders destruktiven Befehlen
- automatische Abschlusskontrolle nach unterstützten Schreiboperationen
- lokales, bereinigtes Audit-Protokoll mit Dateirechten `0600`
- sichere Prozessaufrufe als Argumentliste, ohne Shell-Auswertung
- geführte Eingabeassistenten für Suche, IDs, Limits und Benutzeränderungen
- Rückwärtsnavigation mit `Shift+Tab` in mehrstufigen Assistenten
- globaler Befehlsfilter, Tastaturhilfe und Detailtexte mit Beispielen
- alternative `synadm`-Binärdatei und Konfiguration per Startoption
- geführte Installation beziehungsweise Aktualisierung von `synadm` über `pipx`
- sicherer Erstkonfigurations-Assistent für Server, Admin-Zugriffstoken und API-Einstellungen
- geführter CSV-Import mit Trennzeichenerkennung, Spaltenzuordnung und Vorschau
- Moderationsassistenten für Kontosperren, Shadow-Bans, Geräte und Nachrichtenredaktion
- Raumwerkzeuge für Beitritt, Administratorrechte, Blockierung, Löschstatus und leere Räume
- TUI selbst nur mit Python-Standardbibliothek; die Systempakete bringen zusätzlich die Basis für `synadm`/`pipx` und TLS mit

## Voraussetzungen

- Python 3.10 oder neuer auf Linux/macOS
- OpenSSL, Zertifikatsbundle, `pipx` und Python-Paketwerkzeuge, sofern `synadm` über die TUI installiert oder aktualisiert werden soll
- UTF-8-Terminal; für eingeschränkte Darstellung stehen Kontrast- und Monochromthemen bereit
- `synadm`, wahlweise bereits installiert oder über die TUI nachinstalliert
- ein Admin-Zugriffstoken in der `synadm`-Konfiguration

`synadm` selbst lässt sich üblicherweise mit `pipx install synadm` installieren. Vor dem ersten TUI-Start sollte `synadm version` im selben Benutzerkonto funktionieren.

Die offiziellen DEB- und RPM-Pakete hängen ab Version 0.18 bewusst zusätzlich von den üblichen TLS- und Python-Basispaketen ab. Dadurch werden auf normalen Zielsystemen `ca-certificates`, OpenSSL, Python, pip und `pipx` automatisch mitinstalliert. Das verhindert typische Fehler wie „SSL-Modul nicht vorhanden“, wenn anschließend `synadm` über `pipx` installiert oder HTTPS-Zugriffe durchgeführt werden. Eine manuell selbstgebaute Python-Version ohne SSL-Unterstützung kann dadurch allerdings nicht repariert werden; in diesem Fall muss die Python-Installation selbst korrigiert werden.

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

Der Build erzeugt beide Editionen und die gemeinsame Prüfsummendatei `SHA256SUMS`:

```text
dist/synadm-tui
dist/synadm-tui-thueringen
```

PyInstaller ist bewusst nur eine Build- und keine Laufzeitabhängigkeit. Die nativen Dateien werden für das Betriebssystem und die Prozessorarchitektur des Build-Rechners erstellt. `synadm` selbst bleibt ein separates Programm, kann aber aus der TUI heraus installiert werden.

## DEB- und RPM-Pakete ohne Runner

Aus der nativen Datei lassen sich lokal installierbare Pakete erzeugen. Benötigt werden `dpkg-deb` für Debian-Pakete und `rpmbuild` aus dem Paket `rpm` beziehungsweise `rpm-build` für RPM-Pakete:

```bash
python3 scripts/build_native.py
python3 scripts/build_packages.py
cd dist/packages
sha256sum --check SHA256SUMS
```

Das Ergebnis enthält für beide Editionen jeweils ein DEB- und RPM-Paket:

```text
dist/packages/synadm-tui_<VERSION>_<ARCH>.deb
dist/packages/synadm-tui-<VERSION>-1.<ARCH>.rpm
dist/packages/synadm-tui-thueringen_<VERSION>_<ARCH>.deb
dist/packages/synadm-tui-thueringen-<VERSION>-1.<ARCH>.rpm
```

Die Build-Architektur wird automatisch auf `amd64`/`x86_64` beziehungsweise `arm64`/`aarch64` abgebildet. Das Skript verweigert die Paketierung, wenn die Versionsnummer einer nativen Datei nicht zu `pyproject.toml` passt.

Die DEB- und RPM-Pakete installieren außerdem je Edition einen grafischen Starter unter `/usr/share/applications/` sowie ein Icon unter `/usr/share/pixmaps/`. Dadurch erscheinen **synadm TUI** und **synadm TUI Thüringen** im Startmenü beziehungsweise Application-Launcher grafischer Linux-Desktops. Eine persönliche Desktop-Verknüpfung kann daraus bei Bedarf kopiert werden:

```bash
cp /usr/share/applications/synadm-tui.desktop ~/Desktop/
chmod +x ~/Desktop/synadm-tui.desktop
```

Für die Thüringen-Edition:

```bash
cp /usr/share/applications/synadm-tui-thueringen.desktop ~/Desktop/
chmod +x ~/Desktop/synadm-tui-thueringen.desktop
```

Offizielle RPM-Builds werden automatisch mit dem Schlüssel
`A589 2362 4002 F769 A768 3FD6 C187 58AE CA92 C968` signiert, wenn dessen privater Teil unter `~/.local/share/synadm-tui/rpm-signing/` vorhanden ist. Im Repository liegt ausschließlich der öffentliche Schlüssel. Fremde lokale Builds bleiben ohne privaten Schlüssel unsigniert.

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

Für GitHub wird ein gemeinsames Repository empfohlen. Pro Version gibt es einen Tag und einen Release; darin liegen Standard Edition und Thüringen Edition als getrennte Assets. So bleiben beide Varianten sichtbar getrennt, werden aber gemeinsam entwickelt, getestet und versioniert.

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

APT wählt automatisch die neueste verfügbare Version. Eine Versionsangabe wie
`synadm-tui=0.21` ist für die normale Installation nicht erforderlich.

Dieser Ablauf wurde mit Version 0.21 in einer isolierten APT-Umgebung geprüft: Signaturprüfung, Paketauflösung, Download, Dateirechte und Programmstart waren erfolgreich.

Fedora, RHEL und kompatible Systeme:

```bash
sudo curl -fsSL https://git.blackwall.ipv64.de/api/packages/pan/generic/synadm-tui-repository/1/synadm-tui.repo \
  -o /etc/yum.repos.d/synadm-tui.repo
sudo dnf install synadm-tui
```

Ab Version 0.16 besitzen die RPM-Pakete eine eingebettete RSA/SHA512-Signatur. Die projektspezifische `.repo`-Datei lässt `gpgcheck=1` aktiviert und verweist auf den zugehörigen öffentlichen Schlüssel. Signatur und Installation werden vor einem Release in Fedora mit DNF5 geprüft.

### Editionen gemeinsam aktualisieren

Standard Edition und Thüringen Edition werden im selben Repository gepflegt. Der neutrale Anwendungskern liegt unter `synadm_tui/`, das Thüringen-Branding als dünnes Overlay unter `synadm_tui_thueringen/`. Vor einem Release werden immer beide Entry-Points, beide nativen Binaries und beide Paketsätze aus demselben Commit gebaut.

## Bedienung

| Taste | Funktion |
|---|---|
| `↑` / `↓`, `k` / `j` | In der aktiven Spalte auswählen |
| `Enter` | Bereich bestätigen beziehungsweise Befehl ausführen |
| Linksklick | Bereich auswählen beziehungsweise angeklickten Befehl direkt öffnen |
| `←`, `Esc`, `h` | Von den Befehlen zurück zur Bereichsauswahl |
| `n` | Benutzer anlegen |
| `i` | CSV-Import öffnen |
| `/` | Benutzer suchen |
| `x` | Benutzer als GDPR-gelöscht deaktivieren |
| `a` | Assistent zum Anlegen eines Raums öffnen |
| `c` | synadm-Konfigurationsassistent öffnen |
| `f` | Befehle über alle Bereiche filtern |
| `?` | Tastaturhilfe anzeigen |
| `t` | Themenauswahl öffnen |
| `Shift+Tab` | Im Assistenten einen Schritt zurückgehen |
| `PgUp` / `PgDn`, `Home` | Ausgabe scrollen |
| `v` | Aktuelle Ergebnistabelle filtern beziehungsweise Filter entfernen |
| `s` | Sortierspalte wählen; erneute Auswahl kehrt die Richtung um |
| `Tab` / `→` | Von der Befehlsliste in die Ergebnistabelle wechseln |
| `Enter` auf Tabellenzeile | Kontextmenü für den ausgewählten Benutzer öffnen |
| `r` | letzten Befehl wiederholen |
| `q` | beenden |
| `Esc` | Eingabe oder Bestätigung abbrechen |

Geführte Assistenten fragen häufige Werte wie Suchtext, Limit und Matrix-ID einzeln ab. Mit `Shift+Tab` geht es zum vorherigen Schritt; `Backspace` tut dies ebenfalls, wenn das aktuelle Eingabefeld bereits leer ist. Erweiterte Argumente werden wie in der Shell geschrieben; Anführungszeichen werden unterstützt. Die Eingabe wird mit `shlex` zerlegt und **nicht** durch eine Shell ausgeführt. Die Reaktionszeit der einzelnen `Esc`-Taste wird auf 35 ms reduziert.

`·` kennzeichnet lesende, `+` schreibende und `!` besonders gefährliche Aktionen. Der Detailbereich erklärt die Auswahl und zeigt ein Beispiel. Für gefährliche Aktionen verlangt die TUI eine zweite Bestätigung. Bei Benutzerlöschung, Gerätelöschung, Nachrichtenredaktion, Raumlöschung und History-Purge muss zusätzlich die betroffene Benutzer- oder Raum-ID exakt erneut eingegeben werden. Trotzdem empfiehlt sich vor großflächigen Verwaltungsaktionen ein aktuelles Synapse-Backup.

Die Erstkonfiguration ist mit `c` sowie unter **Weitere → synadm-Erstkonfiguration** erreichbar. Der Assistent fragt Konfigurationspfad, Admin-Benutzer, Zugriffstoken, Verbindung, API-Pfade, Homeserver-Erkennung, Ausgabeformat, Timeout und TLS-Prüfung ab. Vorhandene Dateien werden vor dem Überschreiben als zeitgestempelte `.bak-*`-Datei gesichert. Das Ergebnis wird atomar mit Dateirechten `0600` gespeichert; ein anschließender Diagnoseaufruf zeigt Erfolg oder Fehlergrund im Detailbereich.

Alternativ bleibt die interaktive Einrichtung von `synadm` auf der Kommandozeile möglich:

```bash
synadm config
synadm matrix login @admin:example.org
```

## Einzelnen Benutzer anlegen

Unter **Benutzer → Benutzer anlegen** oder mit der Kurztaste `n` startet ein Assistent für die Einzelanlage. Er fragt nacheinander Matrix-ID, Startpasswort, Anzeigename, E-Mail-Adresse, Adminstatus, Benutzertyp, Sperrstatus, Avatar-URL und optionale Zusatzargumente ab. Mit `Shift+Tab` kann jeder Schritt wieder zurückgenommen werden.

Technisch verwendet die TUI dafür den von `synadm` vorgesehenen Befehl `synadm user modify`, weil `synadm` damit lokale Benutzer erstellt oder vorhandene Benutzer ändert. Vor dem Ausführen zeigt synadm-tui den fertigen Befehl noch einmal an; Passwörter werden dabei ausgeblendet.

Beispiel:

```bash
synadm user modify @alice:example.org --password 'Start-123' --display-name 'Alice Beispiel' --threepid email alice@example.org
```

## Benutzer aus CSV importieren

Unter **Benutzer → Benutzer aus CSV importieren** führt ein Assistent durch fünf Schritte:

1. UTF-8-CSV-Datei im eingebauten Dateibrowser auswählen
2. automatisch erkanntes Trennzeichen in einem Auswahlmenü prüfen oder ändern und Kopfzeile angeben
3. CSV-Spalten mit `←`/`→` den Zielfeldern zuordnen; eine Tabelle zeigt dabei Kopfzeile und erste Datensätze
4. Behandlung der Benutzer-ID-Domain wählen
5. Benutzer-Vorschau prüfen und Import bestätigen

Unterstützte Zielfelder sind Benutzer-ID, Passwort, Anzeigename, E-Mail, Adminstatus, Benutzertyp, Avatar-URL und Sperrstatus. Nur die Benutzer-ID ist verpflichtend; zusätzlich muss mindestens ein anzulegender Wert vorhanden sein. Wahrheitswerte akzeptieren unter anderem `ja`/`nein`, `true`/`false` und `1`/`0`. Zulässige Benutzertypen sind `regular`, `bot` und `support`.

Für Installationen, bei denen die öffentliche Synapse-API-Domain nicht der Matrix-Homeserver-Domain entspricht, kann der Assistent die Benutzer-IDs passend aufbereiten. Zur Auswahl stehen:

- Benutzer-IDs unverändert aus der CSV übernehmen
- Homeserver-Domain nur ergänzen, wenn sie in der CSV fehlt
- Homeserver-Domain immer setzen und vorhandene Domains ersetzen

Die abzufragende Domain ist der Matrix-`server_name`, also der Teil hinter dem Doppelpunkt in Matrix-IDs wie `@alice:matrix.example.org` — nicht zwingend die öffentliche API-URL.

Beispiel:

```csv
username;password;display_name;email;admin;type
@alice:example.org;Start-123;Alice;alice@example.org;nein;regular
@service:example.org;Bot-456;Service Bot;;nein;bot
```

Der Assistent blendet Passwörter in Vorschau und Ergebnis aus. Da `synadm` im nicht-interaktiven Modus Passwörter über `--password` entgegennimmt, können sie während des kurzen Unterprozesses für andere Prozesse desselben Systems sichtbar sein. CSV-Datei und Host sollten entsprechend geschützt werden; Startpasswörter anschließend wechseln lassen.

Im Dateibrowser öffnet `Enter` ein Verzeichnis beziehungsweise wählt eine CSV-Datei aus. `←` oder `Backspace` wechselt zum Elternverzeichnis. Mit `p` kann weiterhin ein Pfad direkt eingegeben werden.

In Ja/Nein-Dialogen wird die gewünschte Schaltfläche mit `←`/`→` gewählt und mit `Enter` bestätigt. Sicherheitsabfragen starten grundsätzlich auf **Nein**.

## Benutzer löschen

Unter **Benutzer → Benutzer löschen (GDPR)** oder mit `x` lässt sich ein Konto über
den von Synapse unterstützten Löschweg entfernen. Der Assistent fragt zuerst die
vollständige Matrix-ID ab und zeigt anschließend den konkreten Befehl in einer
Sicherheitsabfrage an. **Nein** ist dabei vorausgewählt.

Technisch führt die TUI folgenden `synadm`-Befehl im nicht-interaktiven Modus aus:

```bash
synadm user deactivate --gdpr-erase @alice:example.org
```

Synapse entfernt hierbei aktive Sitzungen, setzt das Passwort zurück, löscht
Drittanbieter-IDs, entfernt das Konto aus beigetretenen Räumen und markiert es als
GDPR-gelöscht. Der interne Datenbankeintrag wird von der Synapse-Admin-API nicht
physisch entfernt. Die Aktion ist destruktiv und sollte nur mit Testkonten oder nach
einer geeigneten Datensicherung ausprobiert werden.

## Räume anlegen

Unter **Räume → Raum anlegen** oder mit `a` öffnet sich ein Assistent für die
Matrix-Client-API. Er fragt Raumname, optionalen Alias und Thema, Sichtbarkeit,
Raumvorlage, einzuladende Matrix-IDs und die Föderationseinstellung ab. Dropdowns
erklären dabei den Unterschied zwischen privaten, vertrauenswürdigen privaten und
öffentlichen Räumen. Mit `Shift+Tab` kann zu jedem vorherigen Schritt zurückgekehrt
werden.

Vor dem Anlegen zeigt die TUI den vollständigen JSON-Inhalt und startet mit
vorausgewähltem **Nein**. Technisch wird der folgende, von `synadm` unterstützte
Matrix-Zugriff verwendet:

```bash
synadm matrix raw client/v3/createRoom --method post --data '{...}'
```

Der konfigurierte Admin-Benutzer wird zum Ersteller des Raums. Sein Zugriffstoken
wird von `synadm` direkt aus der Konfigurationsdatei gelesen und weder in der
Vorschau noch in den Prozessargumenten der TUI wiederholt.

## Moderation und Raumwerkzeuge

Der eigene Bereich **Moderation** bündelt reversible Kontosperren, Shadow-Bans,
Gerätebereinigung und Nachrichtenredaktion. Für alte Geräte steht zuerst ein
Dry-Run bereit. Er zeigt die betroffenen Geräte, ohne Sitzungen oder Zugriffstoken
zu verändern. Erst die getrennte Löschaktion führt die Bereinigung aus.

Unter **Räume** stehen zusätzlich Aliasauflösung, administrativer Raumbeitritt,
Vergabe von Raumadministratorrechten, Power-Level, Blockierungsstatus,
Entsperrung, Löschstatus und die Bereinigung leerer Räume zur Verfügung. Auch bei
leeren Räumen existiert eine eigene Dry-Run-Aktion, bevor tatsächlich gelöscht
wird.

Nach Benutzeränderungen, Sperren, Gerätebereinigungen, Raumbeitritten,
Administratoränderungen und Blockierungen führt die TUI automatisch einen
passenden Leseaufruf aus. Aktion und Abschlusskontrolle erscheinen gemeinsam im
Ergebnisbereich.

## Tabellenansicht

Strukturierte Listen von `synadm` werden als Tabelle angezeigt. `v` setzt einen
Volltextfilter über alle sichtbaren Spalten; eine leere Eingabe entfernt ihn. Mit
`s` wird die Sortierspalte gewählt. Wird dieselbe Spalte erneut gewählt, wechselt
die Sortierrichtung. `PgUp`, `PgDn` und `Home` bewegen sich wie bei normaler
Ausgabe durch größere Ergebnismengen.

Enthält eine Tabellenzeile eine Matrix-Benutzer-ID, kann sie mit `Tab` oder `→`
fokussiert und mit `↑`/`↓` ausgewählt werden. `Enter` öffnet anschließend ein
Kontextmenü für genau diesen Benutzer. Mit der Maus markiert ein einfacher Klick
die Zeile; ein Doppelklick öffnet das Menü direkt. Verfügbar sind unter anderem:

- Details, Profiländerung und Passwort
- Raum-Mitgliedschaften, Medien und aktive Sitzungen
- Sperren und Entsperren
- Geräteprüfung und Gerätebereinigung
- Shadow-Ban setzen oder aufheben
- Nachrichtenredaktion
- GDPR-Löschung

Die ausgewählte Matrix-ID wird in den jeweiligen Assistenten vorausgefüllt.
Gefährliche Aktionen behalten trotzdem ihre Ja/Nein-Abfrage und die zusätzliche
exakte Zieleingabe.

Lange Befehlslisten und Dropdowns scrollen automatisch um die aktuelle Auswahl.
Das Server-Panel wächst auf größeren Terminals und bricht Statusmeldungen sauber
über mehrere eingerückte Zeilen um, damit die Oberfläche trotz der zusätzlichen
Funktionen nicht gestaucht wirkt.

## Audit-Protokoll

Jeder abgeschlossene `synadm`-Befehl wird mit UTC-Zeit, bereinigter Argumentliste,
Ergebniscode und Laufzeit protokolliert. Passwörter und Tokens werden durch
`********` ersetzt. Die Datei besitzt ausschließlich Benutzerrechte (`0600`):

```text
~/.local/state/synadm-tui/audit.jsonl
```

Unter **Weitere → Audit-Protokoll anzeigen** kann die Chronik direkt als filter-
und sortierbare Tabelle geöffnet werden. Mit `XDG_STATE_HOME` lässt sich der
Speicherort entsprechend der XDG-Konvention ändern.

Die Themenauswahl ist jederzeit mit `t` sowie unter **Weitere → Darstellung / Thema wählen** erreichbar. Mit `↑`/`↓` wird die Farbgebung live ausprobiert, `Enter` speichert sie editionsabhängig unter `~/.config/synadm-tui/`, und `Esc` stellt das vorherige Thema wieder her.

Die Standard Edition enthält die generierten Embleme `retro-cyberspace.png` und `hacker-terminal.png`. Unterstützt das Terminal das Kitty-Grafikprotokoll – beispielsweise Kitty, WezTerm oder Ghostty –, erscheint das zum aktiven Thema passende transparente PNG direkt im Detailbereich. Unter Alacritty, innerhalb von Zellij und in anderen 256-Farben-Terminals zeichnet die TUI automatisch eine kompakte farbige Annäherung mit Unicode-Halbblöcken. Nur wenn auch das nicht möglich ist, wird die reine Textgrafik verwendet. Sixel wird dafür nicht benötigt.

## Sicherheit

- `synadm-tui` startet Prozesse ohne Shell und aktiviert den nicht-interaktiven `synadm`-Modus.
- Der Erstkonfigurations-Assistent schreibt den eingegebenen Zugriffstoken ausschließlich in die gewählte `synadm`-Konfigurationsdatei. Er wird verdeckt eingegeben, nicht in der Vorschau angezeigt und nicht als Prozessargument übergeben.
- Neu erzeugte Konfigurationsdateien werden atomar geschrieben und erhalten auf POSIX-Systemen die Dateirechte `0600`.
- Passwörter werden in Eingabe, Vorschau und Ergebnis maskiert.
- Audit-Einträge enthalten keine als Passwort oder Token gekennzeichneten Argumentwerte.
- Beim nicht-interaktiven Benutzerimport muss `synadm` Passwörter kurzzeitig als Prozessargument erhalten. Auf Mehrbenutzersystemen können andere privilegierte Prozesse diese möglicherweise sehen.
- Konfigurationsdateien, `.env`-Dateien und lokale YAML-Konfigurationen sind standardmäßig von Git ausgeschlossen.

## Architektur

| Modul | Aufgabe |
|---|---|
| `app.py` | curses-Oberfläche, Navigation und Assistenten |
| `runner.py` | sichere `synadm`-Prozessausführung |
| `catalog.py` | Bereiche und verfügbare Aktionen |
| `assistants.py` | strukturierte Eingabefelder pro Befehl |
| `room_creation.py` | Validierung und JSON-Aufbau für die Matrix-Raumerstellung |
| `table_view.py` | Extraktion, Filterung, Sortierung und Darstellung strukturierter Ergebnisse |
| `audit.py` | lokales JSONL-Audit mit Geheimnisbereinigung und sicheren Dateirechten |
| `command_help.py` | Beschreibungen, Beispiele und Schreibschutz-Kennzeichnung |
| `configuration.py` | Validierung, Sicherung und atomare synadm-Konfiguration |
| `edition.py` | neutrales Standardprofil und Erweiterungsschnittstelle für Editionen |
| `terminal_image.py` | optionale transparente PNG-Darstellung über das Kitty-Grafikprotokoll |
| `block_art.py` | protokollfreie 256-Farben-Darstellung für Alacritty und Multiplexer |
| `csv_import.py` | CSV-Erkennung, Validierung und Importplanung |
| `file_browser.py` | Dateibrowser für CSV-Dateien |
| `synadm_tui_thueringen/` | Thüringen-Edition als Branding-Overlay mit eigenem Entry-Point |

## Entwicklung

```bash
python3 -m unittest discover -v
python3 -m compileall -q synadm_tui
python3 scripts/build_executable.py
```

Die Tests verwenden ausschließlich die Standardbibliothek und benötigen keinen erreichbaren Synapse-Server. Weitere Hinweise stehen in [CONTRIBUTING.md](CONTRIBUTING.md).

## Lizenz

GPL-3.0-or-later, siehe [LICENSE](LICENSE).
