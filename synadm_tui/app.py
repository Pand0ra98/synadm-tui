"""The curses user interface."""

from __future__ import annotations

import curses
import json
import locale
import os
import queue
import shlex
import shutil
import subprocess
import threading
import textwrap
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .catalog import SECTIONS, Command
from .assistants import fields_for
from .csv_import import (
    FIELDS,
    CsvData,
    CsvImportError,
    ImportEntry,
    build_entries,
    inspect_csv,
    redact_args,
)
from .file_browser import list_entries
from .runner import Result, SynadmRunner, pretty_output


@dataclass(slots=True)
class Selection:
    section: int = 0
    command: int = 0
    output_offset: int = 0


@dataclass(frozen=True, slots=True)
class Activity:
    timestamp: str
    label: str
    ok: bool


class App:
    def __init__(self, runner: SynadmRunner) -> None:
        self.runner = runner
        self.selection = Selection()
        self.focus = "sections"
        self.result: Result | None = None
        self.output = "Bereit. Wähle links einen Bereich und einen Befehl."
        self.status = "synadm gefunden" if runner.available else "synadm nicht gefunden – siehe README"
        self.running = False
        self.events: queue.SimpleQueue[Result] = queue.SimpleQueue()
        self.server_events: queue.SimpleQueue[Result] = queue.SimpleQueue()
        self.server_state = "Nicht geprüft"
        self.server_version = "—"
        self.activities: list[Activity] = []
        self.pending_activity = ""
        self.recheck_server_after_result = False

    def run(self) -> None:
        locale.setlocale(locale.LC_ALL, "")
        curses.wrapper(self._main)

    def _main(self, screen: curses.window) -> None:
        curses.curs_set(0)
        screen.keypad(True)
        screen.timeout(100)
        self._init_colors()
        self._start_server_check()
        while True:
            self._collect_server_status()
            self._collect_result()
            self._draw(screen)
            key = screen.getch()
            if key in (ord("q"), ord("Q")) and not self.running:
                return
            if key == curses.KEY_RESIZE or key == -1:
                continue
            self._handle_key(screen, key)

    @staticmethod
    def _init_colors() -> None:
        if not curses.has_colors():
            return
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_CYAN, -1)
        curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_CYAN)
        curses.init_pair(3, curses.COLOR_GREEN, -1)
        curses.init_pair(4, curses.COLOR_RED, -1)
        curses.init_pair(5, curses.COLOR_YELLOW, -1)

    def _handle_key(self, screen: curses.window, key: int) -> None:
        if not self.running and key in (ord("i"), ord("I")):
            self._select_command("Benutzer", "Benutzer aus CSV importieren")
            self._prepare_command(screen)
            return
        if not self.running and key in (ord("n"), ord("N")):
            self._select_command("Benutzer", "Benutzer ändern")
            self._prepare_command(screen)
            return
        if not self.running and key == ord("/"):
            self._select_command("Benutzer", "Benutzer suchen")
            self._prepare_command(screen)
            return
        if self.focus == "sections":
            if key in (curses.KEY_UP, ord("k")):
                self.selection.section = (self.selection.section - 1) % len(SECTIONS)
                self.selection.command = 0
            elif key in (curses.KEY_DOWN, ord("j")):
                self.selection.section = (self.selection.section + 1) % len(SECTIONS)
                self.selection.command = 0
            elif key in (10, 13, curses.KEY_ENTER, curses.KEY_RIGHT, ord("l"), 9):
                self.focus = "commands"
            return
        if key in (curses.KEY_LEFT, ord("h"), 27):
            self.focus = "sections"
        elif key in (curses.KEY_UP, ord("k")):
            commands = SECTIONS[self.selection.section].commands
            self.selection.command = (self.selection.command - 1) % len(commands)
        elif key in (curses.KEY_DOWN, ord("j")):
            commands = SECTIONS[self.selection.section].commands
            self.selection.command = (self.selection.command + 1) % len(commands)
        elif key == curses.KEY_PPAGE:
            self.selection.output_offset = max(0, self.selection.output_offset - 10)
        elif key == curses.KEY_NPAGE:
            self.selection.output_offset += 10
        elif key in (10, 13, curses.KEY_ENTER) and not self.running:
            self._prepare_command(screen)
        elif key in (ord("r"), ord("R")) and self.result and not self.running:
            args = self._args_from_result(self.result)
            if args is not None:
                self._launch(args)
        elif key == curses.KEY_HOME:
            self.selection.output_offset = 0

    def _prepare_command(self, screen: curses.window) -> None:
        spec = self.current_command
        if spec.action == "csv_import":
            self._csv_import_wizard(screen)
            return
        if spec.action == "install_synadm":
            self._install_synadm(screen)
            return
        if spec.action == "uninstall_synadm":
            self._uninstall_synadm(screen)
            return
        if spec.action == "uninstall_pipx":
            self._uninstall_pipx(screen)
            return
        extra_args = self._command_assistant(screen, spec)
        if extra_args is None:
            return
        args = [*spec.argv, *extra_args]
        if not args:
            self.status = "Bitte einen synadm-Befehl eingeben."
            return
        if spec.dangerous and not self._confirm(screen, args):
            self.status = "Destruktive Aktion abgebrochen"
            return
        self._launch(args)

    def _command_assistant(self, screen: curses.window, spec: Command) -> list[str] | None:
        fields = fields_for(spec.argv, spec.hint)
        if not fields:
            return []
        collected: list[str] = []
        total = len(fields)
        for index, field in enumerate(fields, start=1):
            while True:
                value = self._prompt(
                    screen,
                    f"{spec.title} · {index}/{total}",
                    f"{field.label}: {field.hint}",
                    secret=field.secret,
                )
                if value is None:
                    self.status = "Assistent abgebrochen"
                    return None
                if value.strip() or not field.required:
                    break
                self.status = f"{field.label} ist erforderlich"
            if not value.strip():
                continue
            if field.raw:
                try:
                    collected.extend(shlex.split(value))
                except ValueError as error:
                    self.status = f"Ungültige Optionen: {error}"
                    return None
            else:
                collected.extend(field.prefix)
                collected.append(value.strip())
        if spec.argv == ("user", "modify") and len(collected) == 1:
            self.status = "Zum Anlegen oder Ändern muss mindestens ein Wert angegeben werden."
            return None
        return collected

    def _launch(self, args: list[str]) -> None:
        if self.running:
            return
        self.running = True
        visible_command = redact_args(self.runner.build_command(args))
        self.output = "$ " + " ".join(shlex.quote(part) for part in visible_command) + "\n\nWird ausgeführt …"
        self.status = "Befehl läuft …"
        self.pending_activity = " ".join(args[:3])
        self.selection.output_offset = 0

        def work() -> None:
            self.events.put(self.runner.run(args, structured="--help" not in args and "-h" not in args))

        threading.Thread(target=work, name="synadm-runner", daemon=True).start()

    def _install_synadm(self, screen: curses.window) -> None:
        pipx = shutil.which("pipx")
        if pipx is None:
            python = shutil.which("python3")
            if python is None:
                self.status = "Python 3 und pipx wurden nicht gefunden"
                self.output = "pipx benötigt Python 3. Bitte Python und pip über den System-Paketmanager installieren."
                return
            commands = [
                [python, "-m", "pip", "install", "--user", "pipx"],
                [python, "-m", "pipx", "install", "synadm"],
            ]
            if not self._confirm_package_action(
                screen,
                "pipx fehlt. pipx und anschließend synadm installieren?",
                commands,
            ):
                self.status = "Installation abgebrochen"
                return
            self._launch_package_commands(commands, "pipx + synadm installieren", "pipx und synadm werden installiert …")
            return
        operation = "upgrade" if self._pipx_manages_synadm() else "install"
        command = [pipx, operation, "synadm"]
        question = "synadm aktualisieren?" if operation == "upgrade" else "synadm installieren?"
        if not self._confirm_package_action(screen, question, [command]):
            self.status = "Installation abgebrochen"
            return
        status = "synadm wird installiert …" if operation == "install" else "synadm wird aktualisiert …"
        self._launch_package_commands([command], f"pipx {operation} synadm", status)

    def _uninstall_synadm(self, screen: curses.window) -> None:
        pipx = shutil.which("pipx")
        if pipx is None or not self._pipx_manages_synadm():
            self.status = "Keine pipx-Installation von synadm gefunden"
            self.output = "Nur eine von pipx verwaltete synadm-Installation kann automatisch sauber entfernt werden."
            return
        command = [pipx, "uninstall", "synadm"]
        if not self._confirm_package_action(screen, "synadm wirklich deinstallieren?", [command]):
            self.status = "Deinstallation abgebrochen"
            return
        self._launch_package_commands([command], "synadm deinstallieren", "synadm wird entfernt …")

    def _uninstall_pipx(self, screen: curses.window) -> None:
        pipx = shutil.which("pipx")
        if pipx is None:
            self.status = "pipx wurde nicht gefunden"
            self.output = "Es gibt keine gefundene pipx-Installation zum Entfernen."
            return
        other_apps = sorted(self._pipx_managed_apps() - {"synadm"})
        if other_apps:
            self.status = "pipx wird nicht entfernt: weitere Anwendungen vorhanden"
            self.output = "Folgende pipx-Anwendungen würden ihre Verwaltung verlieren:\n\n" + "\n".join(f"  • {name}" for name in other_apps)
            return
        commands: list[list[str]] = []
        if self._pipx_manages_synadm():
            commands.append([pipx, "uninstall", "synadm"])
        remove_command = self._pipx_remove_command(pipx)
        if remove_command is None:
            self.status = "pipx kann nicht automatisch entfernt werden"
            self.output = "Der Installationsweg von pipx wurde nicht erkannt. Bitte pipx mit dem ursprünglichen Paketmanager entfernen."
            return
        commands.append(remove_command)
        if not self._confirm_package_action(screen, "synadm und pipx vollständig entfernen?", commands):
            self.status = "Deinstallation abgebrochen"
            return
        self._launch_package_commands(commands, "synadm + pipx entfernen", "synadm und pipx werden entfernt …")

    def _launch_package_commands(self, commands: list[list[str]], label: str, status: str) -> None:
        self.running = True
        self.pending_activity = label
        self.recheck_server_after_result = True
        self.status = status
        self.output = "\n".join("$ " + " ".join(shlex.quote(part) for part in command) for command in commands) + "\n\nWird ausgeführt …"
        self.selection.output_offset = 0

        def work() -> None:
            started = time.monotonic()
            stdout_parts: list[str] = []
            stderr_parts: list[str] = []
            returncode = 0
            for command in commands:
                stdout_parts.append("$ " + " ".join(shlex.quote(part) for part in command))
                try:
                    process = subprocess.run(
                        command,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=300,
                        check=False,
                        env={**os.environ, "NO_COLOR": "1"},
                    )
                    if process.stdout.strip():
                        stdout_parts.append(process.stdout.strip())
                    if process.stderr.strip():
                        stderr_parts.append(process.stderr.strip())
                    returncode = process.returncode
                except subprocess.TimeoutExpired:
                    returncode = 124
                    stderr_parts.append("Zeitlimit von 300 Sekunden überschritten.")
                except OSError as error:
                    returncode = 127
                    stderr_parts.append(str(error))
                if returncode != 0:
                    break
            self.events.put(Result(
                ("package-operation", label),
                returncode,
                "\n\n".join(stdout_parts),
                "\n".join(stderr_parts),
                time.monotonic() - started,
            ))

        threading.Thread(target=work, name="synadm-package-manager", daemon=True).start()

    @staticmethod
    def _pipx_manages_synadm() -> bool:
        home = Path.home()
        return any((root / "synadm").is_dir() for root in (
            home / ".local" / "share" / "pipx" / "venvs",
            home / ".local" / "pipx" / "venvs",
        ))

    @staticmethod
    def _pipx_managed_apps() -> set[str]:
        apps: set[str] = set()
        home = Path.home()
        for root in (home / ".local" / "share" / "pipx" / "venvs", home / ".local" / "pipx" / "venvs"):
            try:
                apps.update(path.name for path in root.iterdir() if path.is_dir())
            except OSError:
                continue
        return apps

    @staticmethod
    def _pipx_remove_command(pipx: str) -> list[str] | None:
        resolved = Path(pipx).resolve()
        home = Path.home().resolve()
        if resolved.is_relative_to(home):
            python = shutil.which("python3")
            return [python, "-m", "pip", "uninstall", "-y", "pipx"] if python else None
        if os.geteuid() == 0:
            prefix: list[str] = []
        else:
            sudo = shutil.which("sudo")
            if sudo is None:
                return None
            prefix = [sudo, "-n"]
        if shutil.which("apt-get"):
            return [*prefix, "apt-get", "remove", "-y", "pipx"]
        if shutil.which("dnf"):
            return [*prefix, "dnf", "remove", "-y", "pipx"]
        if shutil.which("pacman"):
            return [*prefix, "pacman", "-R", "--noconfirm", "pipx"]
        return None

    def _csv_import_wizard(self, screen: curses.window) -> None:
        path = self._choose_csv_file(screen)
        if not path:
            self.status = "CSV-Import abgebrochen"
            return
        try:
            detected = inspect_csv(path, has_header=False)
        except CsvImportError as error:
            self._show_error(str(error))
            return
        delimiter = self._choose_delimiter(screen, detected.delimiter)
        if delimiter is None:
            self.status = "CSV-Import abgebrochen"
            return
        has_header = self._ask_yes_no(
            screen,
            "CSV-Import · Kopfzeile",
            "Enthält die erste Zeile Spaltennamen?",
            default=True,
        )
        if has_header is None:
            self.status = "CSV-Import abgebrochen"
            return
        try:
            data = inspect_csv(path, delimiter, has_header=has_header)
        except CsvImportError as error:
            self._show_error(str(error))
            return
        mapping = self._map_csv_columns(screen, data)
        if mapping is None:
            self.status = "CSV-Import abgebrochen"
            return
        try:
            entries = build_entries(data, mapping)
        except CsvImportError as error:
            self._show_error(str(error))
            return
        if not self._confirm_csv_import(screen, data, entries, mapping):
            self.status = "CSV-Import abgebrochen"
            return
        self._launch_csv_import(entries, data.path.name)

    def _launch_csv_import(self, entries: tuple[ImportEntry, ...], filename: str) -> None:
        self.running = True
        self.result = None
        self.selection.output_offset = 0
        self.status = f"Importiere {len(entries)} Benutzer …"
        self.pending_activity = f"CSV-Import ({len(entries)} Benutzer)"
        self.output = f"CSV-Import aus {filename}\n\n{len(entries)} Benutzer werden nacheinander angelegt …"

        def work() -> None:
            started = time.monotonic()
            successes: list[str] = []
            failures: list[tuple[ImportEntry, Result]] = []
            for entry in entries:
                result = self.runner.run(entry.args)
                if result.ok:
                    successes.append(entry.user_id)
                else:
                    failures.append((entry, result))
            lines = [
                "CSV-Import abgeschlossen",
                "",
                f"Erfolgreich: {len(successes)}",
                f"Fehlgeschlagen: {len(failures)}",
            ]
            if successes:
                lines += ["", "Angelegt/aktualisiert:", *[f"  ✓ {user_id}" for user_id in successes]]
            if failures:
                lines += ["", "Fehler:"]
                for entry, result in failures:
                    detail_source = result.stderr.strip() or result.stdout.strip() or "unbekannter Fehler"
                    detail = " ".join(detail_source.splitlines())[:300]
                    lines.append(f"  ✗ Zeile {entry.line}, {entry.user_id}: {detail}")
            self.events.put(Result(
                ("csv-import", filename),
                1 if failures else 0,
                "\n".join(lines),
                "",
                time.monotonic() - started,
            ))

        threading.Thread(target=work, name="synadm-csv-import", daemon=True).start()

    def _choose_csv_file(self, screen: curses.window) -> str | None:
        directory = self._initial_browser_directory()
        selected = 0
        offset = 0
        message = ""
        while True:
            try:
                entries = list_entries(directory)
            except ValueError as error:
                message = str(error)
                directory = directory.parent
                entries = ()
            height, width = screen.getmaxyx()
            visible_height = max(1, height - 9)
            selected = min(selected, max(0, len(entries) - 1))
            if selected < offset:
                offset = selected
            if selected >= offset + visible_height:
                offset = selected - visible_height + 1

            screen.erase()
            self._draw_csv_header(screen, 1, "Datei auswählen")
            self._draw_box(screen, 2, 0, height - 4, width, "CSV-Dateien", True)
            self._safe_add(screen, 3, 2, "Verzeichnis:", curses.A_BOLD | self._color(1))
            self._safe_add(screen, 3, 15, str(directory)[: max(1, width - 17)])
            try:
                screen.hline(4, 1, curses.ACS_HLINE, width - 2, curses.A_DIM)
            except curses.error:
                pass
            if not entries:
                self._safe_add(screen, 6, 3, "Keine CSV-Dateien oder Unterordner gefunden.", curses.A_DIM)
            for row, entry in enumerate(entries[offset : offset + visible_height]):
                index = offset + row
                attr = curses.A_BOLD | self._color(2) if index == selected else curses.A_NORMAL
                self._safe_add(screen, 5 + row, 3, entry.label[: width - 6], attr)
            if entries:
                indicator = f"{selected + 1}/{len(entries)}"
                self._safe_add(screen, 3, width - len(indicator) - 2, indicator, curses.A_DIM)
            self._safe_add(screen, height - 4, 2, message[: width - 4], self._color(4))
            self._safe_add(
                screen,
                height - 1,
                2,
                "↑/↓ Auswahl · Enter öffnen · ←/Backspace hoch · p Pfad eingeben · Esc abbrechen"[: width - 4],
                curses.A_DIM,
            )
            screen.refresh()
            key = screen.getch()
            message = ""
            if key == 27:
                return None
            if key in (curses.KEY_UP, ord("k")) and entries:
                selected = (selected - 1) % len(entries)
            elif key in (curses.KEY_DOWN, ord("j")) and entries:
                selected = (selected + 1) % len(entries)
            elif key in (curses.KEY_LEFT, curses.KEY_BACKSPACE, 127, ord("h")):
                parent = directory.parent
                if parent != directory:
                    directory = parent
                    selected = offset = 0
            elif key in (10, 13, curses.KEY_ENTER) and entries:
                entry = entries[selected]
                if entry.is_dir:
                    directory = entry.path
                    selected = offset = 0
                else:
                    return str(entry.path)
            elif key in (ord("p"), ord("P"), ord("/")):
                manual = self._prompt(
                    screen,
                    "CSV-Datei manuell eingeben",
                    "Absoluter oder relativer Pfad",
                    initial=str(directory) + os.sep,
                )
                if manual:
                    candidate = Path(manual).expanduser()
                    if candidate.is_dir():
                        directory = candidate
                        selected = offset = 0
                    elif candidate.is_file():
                        return str(candidate)
                    else:
                        message = "Pfad wurde nicht gefunden."

    @staticmethod
    def _initial_browser_directory() -> Path:
        try:
            return Path.cwd()
        except OSError:
            return Path.home()

    def _collect_result(self) -> None:
        try:
            result = self.events.get_nowait()
        except queue.Empty:
            return
        self.result = result
        self.running = False
        body = result.stdout if result.stdout.strip() else result.stderr
        self.output = pretty_output(body)
        if result.stdout.strip() and result.stderr.strip():
            self.output += "\n\nHinweise:\n" + result.stderr.strip()
        state = "Erfolgreich" if result.ok else f"Fehler (Exit {result.returncode})"
        self.status = f"{state} · {result.duration:.2f} s"
        label = self.pending_activity or " ".join(result.command[-3:])
        self.activities.insert(0, Activity(datetime.now().strftime("%H:%M:%S"), label, result.ok))
        del self.activities[8:]
        self.pending_activity = ""
        recheck_server = self.recheck_server_after_result
        self.recheck_server_after_result = False
        if result.ok and recheck_server:
            self._start_server_check()

    def _start_server_check(self) -> None:
        if not self.runner.available:
            self.server_state = "synadm fehlt"
            return
        self.server_state = "Prüfe …"

        def work() -> None:
            self.server_events.put(self.runner.run(["version"]))

        threading.Thread(target=work, name="synadm-server-check", daemon=True).start()

    def _collect_server_status(self) -> None:
        try:
            result = self.server_events.get_nowait()
        except queue.Empty:
            return
        if not result.ok:
            self.server_state = "Nicht erreichbar"
            return
        self.server_state = "Verbunden"
        try:
            payload = json.loads(result.stdout)
            self.server_version = str(payload.get("server_version", "—"))
        except (json.JSONDecodeError, AttributeError, TypeError):
            self.server_version = "erkannt"

    def _select_command(self, section_title: str, command_title: str) -> None:
        for section_index, section in enumerate(SECTIONS):
            if section.title != section_title:
                continue
            self.selection.section = section_index
            for command_index, command in enumerate(section.commands):
                if command.title == command_title:
                    self.selection.command = command_index
                    self.focus = "commands"
                    return

    @property
    def current_command(self) -> Command:
        section = SECTIONS[self.selection.section]
        return section.commands[self.selection.command]

    def _draw(self, screen: curses.window) -> None:
        screen.erase()
        height, width = screen.getmaxyx()
        if height < 22 or width < 90:
            self._safe_add(screen, 0, 0, "Terminal zu klein – mindestens 90 × 22 Zeichen benötigt.", curses.A_BOLD)
            self._safe_add(screen, 2, 0, f"Aktuell: {width} × {height}. Mit q beenden.")
            screen.refresh()
            return

        self._safe_add(screen, 0, 1, "synadm TUI", curses.A_BOLD | self._color(1))
        connection_color = self._color(3) if self.server_state == "Verbunden" else self._color(5)
        connection = f"● {self.server_state}"
        self._safe_add(screen, 0, width - len(connection) - 2, connection, curses.A_BOLD | connection_color)
        screen.hline(1, 0, curses.ACS_HLINE, width)

        body_y = 2
        body_height = height - 4
        left_width = min(30, max(24, width // 5))
        command_width = min(42, max(30, width // 3))
        command_x = left_width + 1
        output_x = command_x + command_width + 1
        output_width = width - output_x

        server_height = 6
        sections_height = len(SECTIONS) + 3
        quick_height = body_height - server_height - sections_height
        self._draw_server_panel(screen, body_y, 0, left_width, server_height)
        self._draw_sections(screen, body_y + server_height, 0, left_width, sections_height)
        self._draw_quick_actions(screen, body_y + server_height + sections_height, 0, left_width, quick_height)
        self._draw_commands(screen, body_y, command_x, command_width, body_height)

        details_height = max(11, body_height * 2 // 3)
        activity_height = body_height - details_height
        self._draw_output(screen, body_y, output_x, output_width, details_height)
        self._draw_activity(screen, body_y + details_height, output_x, output_width, activity_height)

        screen.hline(height - 2, 0, curses.ACS_HLINE, width)
        footer = "↑/↓ wählen   Enter öffnen   / suchen   n neu   i CSV-Import   ← zurück   q Ende"
        self._safe_add(screen, height - 1, 2, footer[: width - 4], curses.A_DIM)
        screen.refresh()

    def _draw_sections(self, screen: curses.window, y: int, x: int, width: int, height: int) -> None:
        self._draw_box(screen, y, x, height, width, "Bereiche", self.focus == "sections")
        for index, section in enumerate(SECTIONS):
            if index == self.selection.section and self.focus == "sections":
                attr = curses.A_BOLD | self._color(2)
            elif index == self.selection.section:
                attr = curses.A_BOLD | self._color(1)
            else:
                attr = curses.A_NORMAL
            marker = "› " if index == self.selection.section else "  "
            self._safe_add(screen, y + 1 + index, x + 2, (marker + section.title)[: width - 4], attr)

    def _draw_commands(self, screen: curses.window, y: int, x: int, width: int, height: int) -> None:
        self._draw_box(screen, y, x, height, width, SECTIONS[self.selection.section].title, self.focus == "commands")
        for index, command in enumerate(SECTIONS[self.selection.section].commands[: height - 4]):
            selected = index == self.selection.command
            active = selected and self.focus == "commands"
            attr = self._color(2) | curses.A_BOLD if active else (self._color(5) if command.dangerous else 0)
            marker = "! " if command.dangerous else "  "
            self._safe_add(screen, y + 2 + index, x + 2, (marker + command.title)[: width - 4], attr)
        spec = self.current_command
        if spec.hint:
            self._safe_add(screen, y + height - 2, x + 2, ("Eingabe: " + spec.hint)[: width - 4], curses.A_DIM)

    def _draw_output(self, screen: curses.window, y: int, x: int, width: int, height: int) -> None:
        title = "Details / Ausgabe"
        if self.result:
            title += "  ✓" if self.result.ok else "  ✗"
        self._draw_box(screen, y, x, height, width, title, False)
        lines: list[str] = []
        for raw_line in self.output.expandtabs(4).splitlines() or [""]:
            lines.extend(textwrap.wrap(raw_line, max(1, width - 4), replace_whitespace=False, drop_whitespace=False) or [""])
        max_offset = max(0, len(lines) - (height - 3))
        self.selection.output_offset = min(self.selection.output_offset, max_offset)
        visible = lines[self.selection.output_offset : self.selection.output_offset + height - 3]
        for line_no, line in enumerate(visible):
            self._safe_add(screen, y + 2 + line_no, x + 2, line[: width - 4])
        if max_offset:
            indicator = f"{self.selection.output_offset + 1}–{min(len(lines), self.selection.output_offset + len(visible))}/{len(lines)}"
            self._safe_add(screen, y, x + width - len(indicator) - 2, indicator, curses.A_DIM)

    def _draw_server_panel(self, screen: curses.window, y: int, x: int, width: int, height: int) -> None:
        self._draw_box(screen, y, x, height, width, "Server", False)
        state_color = self._color(3) if self.server_state == "Verbunden" else self._color(5)
        self._safe_add(screen, y + 1, x + 2, f"● {self.server_state}"[: width - 4], curses.A_BOLD | state_color)
        self._safe_add(screen, y + 2, x + 2, f"Synapse {self.server_version}"[: width - 4])
        self._safe_add(screen, y + 3, x + 2, self.status[: width - 4], self._status_color())

    def _draw_quick_actions(self, screen: curses.window, y: int, x: int, width: int, height: int) -> None:
        if height < 3:
            return
        self._draw_box(screen, y, x, height, width, "Schnellaktionen", False)
        actions = (("n", "Benutzer anlegen"), ("i", "CSV importieren"), ("/", "Benutzer suchen"))
        for index, (key, label) in enumerate(actions[: max(0, height - 2)]):
            self._safe_add(screen, y + 1 + index, x + 2, key, curses.A_BOLD | self._color(1))
            self._safe_add(screen, y + 1 + index, x + 5, label[: width - 7])

    def _draw_activity(self, screen: curses.window, y: int, x: int, width: int, height: int) -> None:
        if height < 3:
            return
        self._draw_box(screen, y, x, height, width, "Aktivität", False)
        if not self.activities:
            self._safe_add(screen, y + 1, x + 2, "Noch keine Aktionen in dieser Sitzung", curses.A_DIM)
            return
        for index, activity in enumerate(self.activities[: height - 2]):
            icon = "✓" if activity.ok else "✗"
            color = self._color(3) if activity.ok else self._color(4)
            self._safe_add(screen, y + 1 + index, x + 2, activity.timestamp, curses.A_DIM)
            self._safe_add(screen, y + 1 + index, x + 11, icon, color | curses.A_BOLD)
            self._safe_add(screen, y + 1 + index, x + 13, activity.label[: max(1, width - 15)])

    def _draw_box(
        self,
        screen: curses.window,
        y: int,
        x: int,
        height: int,
        width: int,
        title: str,
        active: bool,
    ) -> None:
        if height < 2 or width < 4:
            return
        attr = self._color(1) | curses.A_BOLD if active else curses.A_DIM
        try:
            screen.hline(y, x + 1, curses.ACS_HLINE, width - 2, attr)
            screen.hline(y + height - 1, x + 1, curses.ACS_HLINE, width - 2, attr)
            screen.vline(y + 1, x, curses.ACS_VLINE, height - 2, attr)
            screen.vline(y + 1, x + width - 1, curses.ACS_VLINE, height - 2, attr)
            screen.addch(y, x, curses.ACS_ULCORNER, attr)
            screen.addch(y, x + width - 1, curses.ACS_URCORNER, attr)
            screen.addch(y + height - 1, x, curses.ACS_LLCORNER, attr)
            screen.addch(y + height - 1, x + width - 1, curses.ACS_LRCORNER, attr)
        except curses.error:
            pass
        self._safe_add(screen, y, x + 2, f" {title} ", curses.A_BOLD | self._color(1))

    def _draw_csv_header(self, screen: curses.window, step: int, title: str) -> None:
        _height, width = screen.getmaxyx()
        self._safe_add(screen, 0, 1, "synadm TUI", curses.A_BOLD | self._color(1))
        self._safe_add(screen, 0, 13, f"CSV-Import · {title}", curses.A_BOLD)
        steps = ((1, "Datei"), (2, "Format"), (3, "Zuordnung"), (4, "Prüfen"))
        rendered = "  ".join(f"{number} {label}" for number, label in steps)
        start = max(1, width - len(rendered) - 2)
        position = start
        for number, label in steps:
            text = f"{number} {label}"
            if number == step:
                attr = curses.A_BOLD | self._color(2)
            elif number < step:
                attr = self._color(3)
            else:
                attr = curses.A_DIM
            self._safe_add(screen, 0, position, text, attr)
            position += len(text) + 2
        try:
            screen.hline(1, 0, curses.ACS_HLINE, width, curses.A_DIM)
        except curses.error:
            pass

    def _draw_csv_backdrop(self, screen: curses.window, step: int, title: str, panel_title: str) -> None:
        screen.erase()
        height, width = screen.getmaxyx()
        self._draw_csv_header(screen, step, title)
        self._draw_box(screen, 2, 0, height - 4, width, panel_title, True)
        self._safe_add(screen, height - 1, 2, "Esc abbrechen", curses.A_DIM)
        screen.refresh()

    def _prompt(
        self,
        screen: curses.window,
        title: str,
        hint: str,
        *,
        initial: str = "",
        secret: bool = False,
    ) -> str | None:
        height, width = screen.getmaxyx()
        box_width = min(width - 4, 76)
        box_height = 7
        y, x = (height - box_height) // 2, (width - box_width) // 2
        window = curses.newwin(box_height, box_width, y, x)
        window.keypad(True)
        value: list[str] = list(initial)
        curses.curs_set(1)
        try:
            while True:
                window.erase()
                window.box()
                self._safe_add(window, 1, 2, title, curses.A_BOLD | self._color(1))
                self._safe_add(window, 2, 2, hint[: box_width - 4], curses.A_DIM)
                shown = "".join(value)
                display = "•" * len(shown) if secret else shown
                self._safe_add(window, 4, 2, display[-(box_width - 5) :])
                self._safe_add(window, 5, 2, "Enter bestätigen · Esc abbrechen", curses.A_DIM)
                window.move(4, min(box_width - 3, 2 + len(display)))
                window.refresh()
                key = window.get_wch()
                if key in ("\n", "\r", curses.KEY_ENTER):
                    return shown
                if key == "\x1b":
                    return None
                if key in (curses.KEY_BACKSPACE, "\b", "\x7f"):
                    if value:
                        value.pop()
                elif isinstance(key, str) and key.isprintable():
                    value.append(key)
        finally:
            curses.curs_set(0)

    def _choose_delimiter(self, screen: curses.window, detected: str) -> str | None:
        options = (
            ("Semikolon", ";"),
            ("Komma", ","),
            ("Tabulator", "\t"),
            ("Senkrechter Strich", "|"),
        )
        selected = next((index for index, (_, value) in enumerate(options) if value == detected), 0)
        opened = False
        height, width = screen.getmaxyx()
        self._draw_csv_backdrop(screen, 2, "Format festlegen", "CSV-Format")
        box_width = min(width - 4, 56)
        box_height = 12
        window = curses.newwin(box_height, box_width, (height - box_height) // 2, (width - box_width) // 2)
        window.keypad(True)
        while True:
            window.erase()
            window.box()
            self._safe_add(window, 1, 2, "CSV-Import · 2/4 · Trennzeichen", curses.A_BOLD | self._color(1))
            self._safe_add(window, 2, 2, "Erkannt – bei Bedarf ändern:", curses.A_DIM)
            label, value = options[selected]
            shown = "TAB" if value == "\t" else value
            field = f"[ {label:<22} {shown:<3}  {'▲' if opened else '▼'} ]"
            self._safe_add(window, 4, 3, field[: box_width - 6], curses.A_BOLD | self._color(2))
            if opened:
                for index, (option_label, option_value) in enumerate(options):
                    option_shown = "TAB" if option_value == "\t" else option_value
                    text = f"  {option_label:<22} {option_shown}"
                    attr = curses.A_BOLD | self._color(2) if index == selected else curses.A_NORMAL
                    self._safe_add(window, 5 + index, 3, text[: box_width - 6], attr)
                help_text = "↑/↓ auswählen · Enter übernehmen · Esc zuklappen"
            else:
                help_text = "Enter Dropdown öffnen · Esc abbrechen"
            self._safe_add(window, box_height - 2, 2, help_text, curses.A_DIM)
            window.refresh()
            key = window.getch()
            if opened and key in (curses.KEY_UP, ord("k")):
                selected = (selected - 1) % len(options)
            elif opened and key in (curses.KEY_DOWN, ord("j")):
                selected = (selected + 1) % len(options)
            elif key in (10, 13, curses.KEY_ENTER):
                if opened:
                    return options[selected][1]
                opened = True
            elif key == 27:
                if opened:
                    opened = False
                else:
                    return None

    def _ask_yes_no(
        self,
        screen: curses.window,
        title: str,
        question: str,
        *,
        default: bool = False,
    ) -> bool | None:
        height, width = screen.getmaxyx()
        self._draw_csv_backdrop(screen, 2, "Format festlegen", "CSV-Format")
        box_width = min(width - 4, 70)
        window = curses.newwin(7, box_width, (height - 7) // 2, (width - box_width) // 2)
        window.keypad(True)
        selected = default
        while True:
            window.erase()
            window.box()
            self._safe_add(window, 1, 2, title, curses.A_BOLD | self._color(1))
            self._safe_add(window, 3, 2, question[: box_width - 4])
            self._safe_add(window, 4, 2, "←/→ auswählen · Enter bestätigen · Esc abbrechen", curses.A_DIM)
            self._draw_yes_no_buttons(window, 5, box_width, selected)
            window.refresh()
            key = window.getch()
            if key in (10, 13, curses.KEY_ENTER):
                return selected
            if key in (curses.KEY_LEFT, curses.KEY_RIGHT, 9, ord("h"), ord("l")):
                selected = not selected
            if key in (ord("j"), ord("J"), ord("y"), ord("Y")):
                return True
            if key in (ord("n"), ord("N")):
                return False
            if key == 27:
                return None

    def _draw_yes_no_buttons(self, window: curses.window, y: int, width: int, selected: bool) -> None:
        yes = "[  Ja  ]"
        no = "[ Nein ]"
        gap = 4
        start = max(2, (width - len(yes) - len(no) - gap) // 2)
        yes_attr = curses.A_BOLD | self._color(2) if selected else curses.A_NORMAL
        no_attr = curses.A_BOLD | self._color(2) if not selected else curses.A_NORMAL
        self._safe_add(window, y, start, yes, yes_attr)
        self._safe_add(window, y, start + len(yes) + gap, no, no_attr)

    def _map_csv_columns(self, screen: curses.window, data: CsvData) -> dict[str, int | None] | None:
        aliases = {
            "user_id": {"user", "username", "userid", "user_id", "benutzer", "benutzer-id", "mxid"},
            "password": {"password", "passwort", "kennwort"},
            "display_name": {"displayname", "display_name", "display name", "anzeigename", "name"},
            "email": {"email", "e-mail", "mail"},
            "admin": {"admin", "administrator", "is_admin"},
            "user_type": {"type", "user_type", "benutzertyp", "typ"},
            "avatar_url": {"avatar", "avatar_url", "avatar-url"},
            "locked": {"locked", "lock", "gesperrt", "sperre"},
        }
        mapping: dict[str, int | None] = {}
        for field in FIELDS:
            mapping[field.key] = next(
                (index for index, label in enumerate(data.labels) if label.strip().lower() in aliases[field.key]),
                None,
            )
        selected = 0
        message = ""
        while True:
            screen.erase()
            height, width = screen.getmaxyx()
            self._draw_csv_header(screen, 3, "Spalten zuordnen")
            self._draw_box(screen, 2, 0, height - 4, width, "Feldzuordnung", True)
            delimiter_name = "Tab" if data.delimiter == "\t" else data.delimiter
            self._safe_add(screen, 3, 2, f"Datei: {data.path}  ·  Trennzeichen: {delimiter_name!r}  ·  Datensätze: {len(data.rows)}")
            self._safe_add(screen, 4, 2, "Jedem Zielfeld kann eine CSV-Spalte zugeordnet werden.", curses.A_DIM)
            for index, field in enumerate(FIELDS):
                y = 6 + index
                if y >= height - 5:
                    break
                column = mapping[field.key]
                label = "— nicht importieren —" if column is None else f"{column + 1}: {data.labels[column]}"
                required = " *" if field.required else ""
                attr = curses.A_BOLD | self._color(2) if index == selected else curses.A_NORMAL
                self._safe_add(screen, y, 3, f"{field.title}{required}"[:27], attr)
                self._safe_add(screen, y, 31, label[: max(1, width - 34)], attr)
            if message:
                self._safe_add(screen, 14, 2, message[: width - 4], self._color(4))
            self._draw_csv_preview(
                screen,
                data,
                mapping[FIELDS[selected].key],
                password_column=mapping.get("password"),
                y=15,
                width=width,
                height=max(0, height - 18),
            )
            self._safe_add(screen, height - 1, 2, "↑/↓ Feld · ←/→ Spalte · Enter übernehmen · Esc abbrechen", curses.A_DIM)
            screen.refresh()
            key = screen.getch()
            if key == 27:
                return None
            if key in (curses.KEY_UP, ord("k")):
                selected = (selected - 1) % len(FIELDS)
            elif key in (curses.KEY_DOWN, ord("j")):
                selected = (selected + 1) % len(FIELDS)
            elif key in (curses.KEY_LEFT, curses.KEY_RIGHT, ord("h"), ord("l")):
                field = FIELDS[selected]
                choices: list[int | None] = [None, *range(len(data.labels))]
                current = choices.index(mapping[field.key])
                delta = -1 if key in (curses.KEY_LEFT, ord("h")) else 1
                mapping[field.key] = choices[(current + delta) % len(choices)]
                message = ""
            elif key in (10, 13, curses.KEY_ENTER):
                if mapping["user_id"] is None:
                    message = "Die mit * markierte Benutzer-ID muss zugeordnet werden."
                else:
                    return mapping

    def _draw_csv_preview(
        self,
        screen: curses.window,
        data: CsvData,
        focus_column: int | None,
        *,
        password_column: int | None,
        y: int,
        width: int,
        height: int,
    ) -> None:
        if height < 2:
            return
        self._safe_add(screen, y, 2, "CSV-VORSCHAU", curses.A_BOLD | self._color(1))
        if height < 3:
            return
        column_count = len(data.labels)
        max_visible = max(1, (width - 4) // 16)
        visible_count = min(column_count, max_visible)
        focus = focus_column if focus_column is not None else 0
        start = max(0, min(focus - visible_count // 2, column_count - visible_count))
        columns = list(range(start, start + visible_count))
        cell_width = max(8, (width - 4) // visible_count)
        if start > 0:
            self._safe_add(screen, y, 15, "← weitere", curses.A_DIM)
        if start + visible_count < column_count:
            self._safe_add(screen, y, width - 12, "weitere →", curses.A_DIM)
        for position, column in enumerate(columns):
            x = 2 + position * cell_width
            selected = column == focus_column
            attr = curses.A_BOLD | self._color(2) if selected else curses.A_BOLD
            header = f"{column + 1}: {data.labels[column]}"
            self._safe_add(screen, y + 1, x, header[: cell_width - 1], attr)
        row_limit = max(0, height - 2)
        for row_index, row in enumerate(data.rows[:row_limit]):
            for position, column in enumerate(columns):
                x = 2 + position * cell_width
                value = row[column]
                if column == password_column and value:
                    value = "********"
                self._safe_add(screen, y + 2 + row_index, x, value[: cell_width - 1])

    def _confirm_csv_import(
        self,
        screen: curses.window,
        data: CsvData,
        entries: tuple[ImportEntry, ...],
        mapping: dict[str, int | None],
    ) -> bool:
        height, width = screen.getmaxyx()
        self._draw_csv_backdrop(screen, 4, "Import prüfen", "Zusammenfassung")
        box_height = min(height - 2, 16)
        box_width = min(width - 4, 82)
        window = curses.newwin(box_height, box_width, (height - box_height) // 2, (width - box_width) // 2)
        window.keypad(True)
        selected = False
        while True:
            window.erase()
            window.box()
            self._safe_add(window, 1, 2, "CSV-Import · 4/4 · Vorschau", curses.A_BOLD | self._color(5))
            mapped = [field.title for field in FIELDS if mapping.get(field.key) is not None]
            self._safe_add(window, 3, 2, f"{len(entries)} Benutzer · Felder: {', '.join(mapped)}"[: box_width - 4])
            self._safe_add(window, 5, 2, "Die ersten Datensätze:", curses.A_BOLD)
            for index, entry in enumerate(entries[: min(5, box_height - 9)]):
                display_col = mapping.get("display_name")
                display = data.rows[index][display_col] if display_col is not None else ""
                suffix = f"  ({display})" if display else ""
                self._safe_add(window, 6 + index, 4, f"• {entry.user_id}{suffix}"[: box_width - 8])
            self._safe_add(window, box_height - 3, 2, "Import starten?  ←/→ auswählen · Enter bestätigen", curses.A_DIM)
            self._draw_yes_no_buttons(window, box_height - 2, box_width, selected)
            window.refresh()
            key = window.getch()
            if key in (10, 13, curses.KEY_ENTER):
                return selected
            if key in (curses.KEY_LEFT, curses.KEY_RIGHT, 9, ord("h"), ord("l")):
                selected = not selected
            if key in (ord("j"), ord("J"), ord("y"), ord("Y")):
                return True
            if key in (ord("n"), ord("N"), 27):
                return False

    def _show_error(self, message: str) -> None:
        self.status = "CSV-Import konnte nicht vorbereitet werden"
        self.output = "CSV-Fehler:\n\n" + message
        self.selection.output_offset = 0

    def _confirm(self, screen: curses.window, args: list[str]) -> bool:
        height, width = screen.getmaxyx()
        box_width = min(width - 4, 72)
        window = curses.newwin(8, box_width, (height - 8) // 2, (width - box_width) // 2)
        window.keypad(True)
        selected = False
        while True:
            window.erase()
            window.box()
            self._safe_add(window, 1, 2, "Destruktive Aktion", curses.A_BOLD | self._color(4))
            safe_args = redact_args(args)
            self._safe_add(window, 3, 2, "synadm " + " ".join(safe_args), self._color(5))
            self._safe_add(window, 5, 2, "Wirklich ausführen?  ←/→ auswählen · Enter bestätigen", curses.A_DIM)
            self._draw_yes_no_buttons(window, 6, box_width, selected)
            window.refresh()
            key = window.getch()
            if key in (10, 13, curses.KEY_ENTER):
                return selected
            if key in (curses.KEY_LEFT, curses.KEY_RIGHT, 9, ord("h"), ord("l")):
                selected = not selected
            if key in (ord("j"), ord("J"), ord("y"), ord("Y")):
                return True
            if key in (ord("n"), ord("N"), 27):
                return False

    def _confirm_package_action(self, screen: curses.window, question: str, commands: list[list[str]]) -> bool:
        height, width = screen.getmaxyx()
        box_width = min(width - 4, 76)
        box_height = 10 + max(0, len(commands) - 1)
        window = curses.newwin(box_height, box_width, (height - box_height) // 2, (width - box_width) // 2)
        window.keypad(True)
        selected = False
        while True:
            window.erase()
            window.box()
            self._safe_add(window, 1, 2, "Paketverwaltung", curses.A_BOLD | self._color(5))
            self._safe_add(window, 3, 2, question, curses.A_BOLD)
            for row, command in enumerate(commands, start=4):
                self._safe_add(window, row, 2, "$ " + " ".join(shlex.quote(part) for part in command), self._color(1))
            hint_row = 5 + len(commands)
            self._safe_add(window, hint_row, 2, "Benötigt ggf. Internetzugriff und ändert die pipx-Umgebung.", curses.A_DIM)
            self._safe_add(window, hint_row + 1, 2, "←/→ auswählen · Enter bestätigen · Esc abbrechen", curses.A_DIM)
            self._draw_yes_no_buttons(window, hint_row + 2, box_width, selected)
            window.refresh()
            key = window.getch()
            if key in (10, 13, curses.KEY_ENTER):
                return selected
            if key in (curses.KEY_LEFT, curses.KEY_RIGHT, 9, ord("h"), ord("l")):
                selected = not selected
            elif key in (ord("j"), ord("J"), ord("y"), ord("Y")):
                return True
            elif key in (ord("n"), ord("N"), 27):
                return False

    def _status_color(self) -> int:
        if self.running:
            return self._color(5)
        if "Fehler" in self.status or "nicht gefunden" in self.status:
            return self._color(4)
        return self._color(3)

    def _color(self, pair: int) -> int:
        return curses.color_pair(pair) if curses.has_colors() else 0

    @staticmethod
    def _safe_add(window: curses.window, y: int, x: int, text: str, attr: int = 0) -> None:
        height, width = window.getmaxyx()
        if y < 0 or y >= height or x < 0 or x >= width:
            return
        try:
            window.addnstr(y, x, text, max(0, width - x - 1), attr)
        except curses.error:
            pass

    def _args_from_result(self, result: Result) -> list[str] | None:
        command = list(result.command)
        try:
            batch = command.index("--batch")
        except ValueError:
            return None
        args = command[batch + 1 :]
        if args[:2] == ["--output", "json"]:
            args = args[2:]
        if args[:2] == ["--config-file", self.runner.config_file]:
            args = args[2:]
        return args
