# Mitwirken

Beiträge sind willkommen. Bitte halte Änderungen klein, nachvollziehbar und durch Tests abgesichert.

## Entwicklungsumgebung

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m unittest discover -v
```

Die TUI lässt sich anschließend direkt mit `synadm-tui` starten. Für reine Oberflächentests kann über `--synadm` auch ein kontrolliertes Testprogramm angegeben werden.

## Vor einem Commit

```bash
python -m compileall -q synadm_tui tests
python -m unittest discover -v
```

- Keine Tokens, Passwörter oder produktiven `synadm`-Konfigurationen committen.
- Neue Verwaltungsaktionen müssen destruktive Auswirkungen sichtbar kennzeichnen.
- Änderungen am CSV-Import benötigen Tests für Parser und Argumenterzeugung.
- Die Anwendung soll ohne zusätzliche Python-Laufzeitabhängigkeiten bleiben.
