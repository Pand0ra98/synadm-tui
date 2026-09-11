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
import textwrap
import threading
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

from .assistants import fields_for
from .audit import append_audit, audit_path
from .block_art import load_block_cells
from .catalog import SECTIONS, Command
from .command_help import command_info
from .configuration import (
    OUTPUT_FORMATS,
    SynadmConfig,
    backup_synadm_config,
    write_synadm_config,
)
from .csv_import import (
    FIELDS,
    CsvData,
    CsvImportError,
    ImportEntry,
    build_entries,
    inspect_csv,
    normalize_homeserver,
    redact_args,
)
from .edition import STANDARD_EDITION, Edition
from .fake_synadm import FakeSynadmRunner
from .file_browser import list_entries
from .room_creation import RoomCreation, RoomCreationError, parse_invitees
from .runner import Result, SynadmRunner, pretty_output
from .table_view import TableView
from .terminal_image import (
    kitty_delete_sequence,
    kitty_render_sequence,
    supports_kitty_graphics,
    theme_image_path,
    write_terminal_sequence,
)


@dataclass(frozen=True, slots=True)
class Theme:
    key: str
    name: str
    badge: str
    palette: tuple[tuple[int, int], ...]
    art: tuple[str, ...]
    ready_label: str
    image_path: Path | None = None
    block_path: Path | None = None

CYBERSPACE_ART = (
    "       /\\  /\\  /\\",
    "  ____/  \\/  \\/  \\____",
    " /   N E O N   G R I D    \\",
    "|  +---+---+---+---+---+   |",
    "| /___/___/___/___/___/|   |",
    "|/___/___/___/___/___/ |   |",
    "+------------------------+",
)

MATRIX_ART = (
    "  01001 10110 00101 11001",
    "   10110  THE MATRIX  011",
    "  00101 10111 01010 10010",
    "   11  FOLLOW THE WHITE 01",
    "  010  RABBIT  101  00110",
    "   10110 00101 11100 010",
    "  00101 11010 01001 10111",
)

HACKER_ART = (
    "  +------------------------+",
    "  | root@synadm:~# ./tui  |",
    "  | ACCESS: AUTHORIZED     |",
    "  | CHANNEL: ENCRYPTED     |",
    "  | TRACE:   DISABLED      |",
    "  | _                      |",
    "  +------------------------+",
)

ACCESSIBLE_ART = (
    "  +========================+",
    "  |   ACCESSIBLE CONSOLE   |",
    "  |   HIGH CONTRAST MODE   |",
    "  |   STATUS: READY        |",
    "  +========================+",
)

THEMES = (
    Theme(
        "cyberspace",
        "Retro Cyberspace 198X",
        "CYBERSPACE",
        (
            (curses.COLOR_MAGENTA, -1), (curses.COLOR_BLACK, curses.COLOR_MAGENTA),
            (curses.COLOR_CYAN, -1), (curses.COLOR_RED, -1),
            (curses.COLOR_YELLOW, -1), (curses.COLOR_WHITE, -1),
            (curses.COLOR_CYAN, -1), (curses.COLOR_BLACK, curses.COLOR_MAGENTA),
            (curses.COLOR_MAGENTA, curses.COLOR_WHITE),
        ),
        CYBERSPACE_ART,
        "WELCOME TO CYBERSPACE // 198X ONLINE",
    ),
    Theme(
        "matrix",
        "Matrix",
        "MATRIX",
        (
            (curses.COLOR_GREEN, -1), (curses.COLOR_BLACK, curses.COLOR_GREEN),
            (curses.COLOR_GREEN, -1), (curses.COLOR_RED, -1),
            (curses.COLOR_YELLOW, -1), (curses.COLOR_GREEN, -1),
            (curses.COLOR_GREEN, -1), (curses.COLOR_BLACK, curses.COLOR_GREEN),
            (curses.COLOR_GREEN, curses.COLOR_WHITE),
        ),
        MATRIX_ART,
        "WAKE UP, ADMIN // THE MATRIX HAS YOU",
    ),
    Theme(
        "hacker",
        "Hacker Terminal",
        "ROOT CONSOLE",
        (
            (curses.COLOR_YELLOW, -1), (curses.COLOR_BLACK, curses.COLOR_YELLOW),
            (curses.COLOR_GREEN, -1), (curses.COLOR_RED, -1),
            (curses.COLOR_CYAN, -1), (curses.COLOR_WHITE, -1),
            (curses.COLOR_YELLOW, -1), (curses.COLOR_BLACK, curses.COLOR_YELLOW),
            (curses.COLOR_YELLOW, curses.COLOR_WHITE),
        ),
        HACKER_ART,
        "ROOT CONSOLE // SECURE SESSION READY",
    ),
    Theme(
        "high-contrast",
        "Hoher Kontrast",
        "HIGH CONTRAST",
        (
            (curses.COLOR_WHITE, -1), (curses.COLOR_BLACK, curses.COLOR_WHITE),
            (curses.COLOR_CYAN, -1), (curses.COLOR_RED, -1),
            (curses.COLOR_YELLOW, -1), (curses.COLOR_WHITE, -1),
            (curses.COLOR_WHITE, -1), (curses.COLOR_BLACK, curses.COLOR_WHITE),
            (curses.COLOR_BLACK, curses.COLOR_WHITE),
        ),
        ACCESSIBLE_ART,
        "HIGH CONTRAST // SYSTEM READY",
    ),
    Theme(
        "monochrome",
        "Monochrom",
        "MONO CONSOLE",
        (
            (curses.COLOR_WHITE, -1), (curses.COLOR_BLACK, curses.COLOR_WHITE),
            (curses.COLOR_WHITE, -1), (curses.COLOR_WHITE, -1),
            (curses.COLOR_WHITE, -1), (curses.COLOR_WHITE, -1),
            (curses.COLOR_WHITE, -1), (curses.COLOR_BLACK, curses.COLOR_WHITE),
            (curses.COLOR_BLACK, curses.COLOR_WHITE),
        ),
        ACCESSIBLE_ART,
        "MONOCHROME CONSOLE // SYSTEM READY",
    ),
)
THEMES_BY_KEY = {theme.key: theme for theme in THEMES}


class WizardBack:
    """Sentinel used by dialogs to request navigation to the previous wizard step."""

    __slots__ = ()


WIZARD_BACK: Final = WizardBack()


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


@dataclass(frozen=True, slots=True)
class PanelLayout:
    body_y: int
    body_height: int
    left_width: int
    server_height: int
    sections_y: int
    sections_height: int
    quick_y: int
    quick_height: int
    command_x: int
    command_width: int


class App:
    def __init__(
        self,
        runner: SynadmRunner,
        edition: Edition = STANDARD_EDITION,
        extra_themes: tuple[Theme, ...] = (),
    ) -> None:
        self.runner = runner
        self.live_runner: SynadmRunner = runner if not runner.demo_mode else SynadmRunner()
        self.demo_runner: FakeSynadmRunner | None = runner if isinstance(runner, FakeSynadmRunner) else None
        self.edition = edition
        self.themes_by_key = dict(THEMES_BY_KEY)
        self.themes_by_key.update((theme.key, theme) for theme in extra_themes)
        missing = tuple(key for key in edition.theme_keys if key not in self.themes_by_key)
        if missing:
            raise ValueError(f"Theme nicht registriert: {', '.join(missing)}")
        self.available_themes = tuple(self.themes_by_key[key] for key in edition.theme_keys)
        self.theme = self._load_theme(edition, self.themes_by_key)
        self.selection = Selection()
        self.focus = "sections"
        self.result: Result | None = None
        self.table_view: TableView | None = None
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
        self.show_command_details = False
        self.config_test_pending = False
        self.inline_images_supported = supports_kitty_graphics()
        self.inline_image_signature: tuple[object, ...] | None = None
        self.pending_inline_image: tuple[Path, int, int, int, int] | None = None
        self.block_color_pairs: dict[tuple[int, int], int] = {}

    @property
    def brand(self) -> str:
        label = "S Y N A D M  //  T U I"
        if self.runner.demo_mode:
            label += "  //  D E M O"
        return label

    @property
    def compact_brand(self) -> str:
        label = "synadm TUI"
        if self.runner.demo_mode:
            label += " // DEMO"
        return label

    def run(self) -> None:
        locale.setlocale(locale.LC_ALL, "")
        curses.wrapper(self._main)

    def _main(self, screen: curses.window) -> None:
        if hasattr(curses, "set_escdelay"):
            curses.set_escdelay(35)
        curses.curs_set(0)
        screen.keypad(True)
        mouse_events = curses.BUTTON1_CLICKED | curses.BUTTON1_DOUBLE_CLICKED
        try:
            curses.mousemask(mouse_events)
            if hasattr(curses, "mouseinterval"):
                curses.mouseinterval(150)
        except curses.error:
            pass
        screen.timeout(100)
        self._init_colors()
        self._start_server_check()
        while True:
            self._collect_server_status()
            self._collect_result()
            self._draw(screen)
            key = screen.getch()
            if key in (ord("q"), ord("Q")) and not self.running:
                self._clear_inline_image()
                return
            if key == curses.KEY_RESIZE or key == -1:
                continue
            self._handle_key(screen, key)

    def _init_colors(self) -> None:
        self.block_color_pairs.clear()
        if not curses.has_colors():
            return
        curses.start_color()
        curses.use_default_colors()
        for pair_number, (foreground, background) in enumerate(self.theme.palette, start=1):
            curses.init_pair(pair_number, foreground, background)

    @staticmethod
    def _theme_config_path(edition: Edition = STANDARD_EDITION) -> Path:
        configured = os.environ.get("XDG_CONFIG_HOME")
        base = Path(configured).expanduser() if configured else Path.home() / ".config"
        return base / "synadm-tui" / f"theme-{edition.key}"

    @classmethod
    def _load_theme(
        cls,
        edition: Edition = STANDARD_EDITION,
        themes_by_key: dict[str, Theme] | None = None,
    ) -> Theme:
        try:
            key = cls._theme_config_path(edition).read_text(encoding="utf-8").strip()
        except OSError:
            key = edition.default_theme
        if key not in edition.theme_keys:
            key = edition.default_theme
        registry = THEMES_BY_KEY if themes_by_key is None else themes_by_key
        return registry[key]

    @classmethod
    def _save_theme(cls, theme: Theme, edition: Edition = STANDARD_EDITION) -> bool:
        path = cls._theme_config_path(edition)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(theme.key + "\n", encoding="utf-8")
        except OSError:
            return False
        return True

    def _handle_key(self, screen: curses.window, key: int) -> None:
        if key == curses.KEY_MOUSE:
            self._handle_mouse(screen)
            return
        if not self.running and self.focus == "table" and self.table_view is not None:
            if key in (curses.KEY_LEFT, ord("h"), 27, 9):
                self.focus = "commands"
                return
            if key in (curses.KEY_UP, ord("k")):
                self.table_view.move(-1)
                return
            if key in (curses.KEY_DOWN, ord("j")):
                self.table_view.move(1)
                return
            if key == curses.KEY_PPAGE:
                self.table_view.move(-10)
                return
            if key == curses.KEY_NPAGE:
                self.table_view.move(10)
                return
            if key == curses.KEY_HOME:
                self.table_view.selected = 0
                return
            if key in (10, 13, curses.KEY_ENTER, ord("m"), ord("M")):
                self._open_user_context_menu(screen)
                return
        if not self.running and key in (ord("?"),):
            self._clear_inline_image()
            self._show_keyboard_help(screen)
            return
        if not self.running and key in (ord("c"), ord("C")):
            self._clear_inline_image()
            self._configure_synadm(screen)
            return
        if not self.running and key in (ord("f"), ord("F")):
            self._clear_inline_image()
            self._command_palette(screen)
            return
        if not self.running and key in (ord("t"), ord("T")):
            self._clear_inline_image()
            self._choose_theme(screen)
            return
        if not self.running and key in (ord("d"), ord("D")):
            self._clear_inline_image()
            self._toggle_demo_mode()
            return
        if not self.running and self.table_view is not None and key in (ord("v"), ord("V")):
            value = self._prompt(
                screen,
                "Tabelle filtern",
                "Suchtext; leer entfernt den Filter",
                initial=self.table_view.filter_text,
            )
            if isinstance(value, str):
                self.table_view.filter_text = value
                self.table_view.selected = 0
                self.selection.output_offset = 0
                self.status = f"Tabellenfilter: {value or 'aus'}"
            return
        if not self.running and self.table_view is not None and key in (ord("s"), ord("S")):
            options = tuple((column, column) for column in self.table_view.columns)
            selected = self._select_dialog_option(
                screen,
                "Tabelle sortieren",
                "Spalte auswählen; erneute Auswahl kehrt die Richtung um:",
                options,
                self.table_view.sort_key,
            )
            if isinstance(selected, str):
                self.table_view.select_sort(selected)
                self.selection.output_offset = 0
                self.status = f"Sortiert nach {selected}"
            return
        if not self.running and key in (ord("i"), ord("I")):
            self._select_command("Benutzer", "Benutzer aus CSV importieren")
            self._prepare_command(screen)
            return
        if not self.running and key in (ord("n"), ord("N")):
            self._select_command("Benutzer", "Benutzer anlegen")
            self._prepare_command(screen)
            return
        if not self.running and key == ord("/"):
            self._select_command("Benutzer", "Benutzer suchen")
            self._prepare_command(screen)
            return
        if not self.running and key in (ord("x"), ord("X")):
            self._select_command("Benutzer", "Benutzer löschen (GDPR)")
            self._prepare_command(screen)
            return
        if not self.running and key in (ord("a"), ord("A")):
            self._select_command("Räume", "Raum anlegen")
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
                self.show_command_details = True
            return
        if self.table_view is not None and key in (curses.KEY_RIGHT, 9):
            self.focus = "table"
            self.show_command_details = False
        elif key in (curses.KEY_LEFT, ord("h"), 27):
            self.focus = "sections"
            self.show_command_details = False
        elif key in (curses.KEY_UP, ord("k")):
            commands = SECTIONS[self.selection.section].commands
            self.selection.command = (self.selection.command - 1) % len(commands)
            self.show_command_details = True
        elif key in (curses.KEY_DOWN, ord("j")):
            commands = SECTIONS[self.selection.section].commands
            self.selection.command = (self.selection.command + 1) % len(commands)
            self.show_command_details = True
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

    @staticmethod
    def _panel_layout(height: int, width: int) -> PanelLayout | None:
        if height < 22 or width < 90:
            return None
        body_y = 2
        body_height = height - 4
        left_width = min(36, max(28, width // 4))
        command_width = min(42, max(30, width // 3))
        sections_height = len(SECTIONS) + 3
        # Grow the server panel on ordinary terminals while preserving at
        # least one quick action at the documented minimum terminal size.
        server_height = max(
            6,
            min(10, body_height // 3, body_height - sections_height - 3),
        )
        quick_height = body_height - server_height - sections_height
        sections_y = body_y + server_height
        return PanelLayout(
            body_y=body_y,
            body_height=body_height,
            left_width=left_width,
            server_height=server_height,
            sections_y=sections_y,
            sections_height=sections_height,
            quick_y=sections_y + sections_height,
            quick_height=quick_height,
            command_x=left_width + 1,
            command_width=command_width,
        )

    def _handle_mouse(self, screen: curses.window) -> None:
        if self.running:
            return
        try:
            _mouse_id, mouse_x, mouse_y, _z, button_state = curses.getmouse()
        except curses.error:
            return
        accepted = curses.BUTTON1_CLICKED | curses.BUTTON1_DOUBLE_CLICKED
        if not button_state & accepted:
            return
        height, width = screen.getmaxyx()
        layout = self._panel_layout(height, width)
        if layout is None:
            return

        section_index = mouse_y - (layout.sections_y + 1)
        if 0 <= mouse_x < layout.left_width and 0 <= section_index < len(SECTIONS):
            self.selection.section = section_index
            self.selection.command = 0
            self.selection.output_offset = 0
            self.focus = "commands"
            self.show_command_details = True
            return

        command_index = mouse_y - (layout.body_y + 2)
        commands = SECTIONS[self.selection.section].commands
        command_start, command_end = self._command_viewport(
            len(commands), self.selection.command, layout.body_height - 4
        )
        visible_commands = commands[command_start:command_end]
        if (
            layout.command_x <= mouse_x < layout.command_x + layout.command_width
            and 0 <= command_index < len(visible_commands)
        ):
            self.selection.command = command_start + command_index
            self.selection.output_offset = 0
            self.focus = "commands"
            self.show_command_details = True
            self._prepare_command(screen)
            return

        quick_index = mouse_y - (layout.quick_y + 1)
        quick_actions = (
            ("Benutzer", "Benutzer anlegen"),
            ("Benutzer", "Benutzer aus CSV importieren"),
            ("Benutzer", "Benutzer suchen"),
            ("Benutzer", "Benutzer löschen (GDPR)"),
            ("Räume", "Raum anlegen"),
        )
        if 0 <= mouse_x < layout.left_width and 0 <= quick_index < len(quick_actions):
            self._select_command(*quick_actions[quick_index])
            self.show_command_details = True
            self._prepare_command(screen)
            return

        if self.table_view is not None:
            output_x = layout.command_x + layout.command_width + 1
            output_width = width - output_x
            details_height = max(11, layout.body_height * 2 // 3)
            if (
                output_x <= mouse_x < output_x + output_width
                and layout.body_y < mouse_y < layout.body_y + details_height - 1
            ):
                line_index = mouse_y - (layout.body_y + 2) + self.selection.output_offset
                row_index = line_index - 3
                rows = self.table_view.visible_rows()
                if 0 <= row_index < len(rows):
                    self.table_view.selected = row_index
                    self.focus = "table"
                    self.show_command_details = False
                    if button_state & curses.BUTTON1_DOUBLE_CLICKED:
                        self._open_user_context_menu(screen)

    def _prepare_command(
        self,
        screen: curses.window,
        defaults: dict[str, str] | None = None,
    ) -> None:
        self._clear_inline_image()
        spec = self.current_command
        if spec.action == "csv_import":
            self._csv_import_wizard(screen)
            return
        if spec.action == "create_user":
            self._create_user_wizard(screen)
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
        if spec.action == "choose_theme":
            self._choose_theme(screen)
            return
        if spec.action == "configure_synadm":
            self._configure_synadm(screen)
            return
        if spec.action == "create_room":
            self._create_room_wizard(screen)
            return
        if spec.action == "show_audit":
            self._show_audit()
            return
        if spec.action == "toggle_demo":
            self._toggle_demo_mode()
            return
        extra_args = self._command_assistant(screen, spec, defaults)
        if extra_args is None:
            return
        args = [*spec.argv, *extra_args]
        if not args:
            self.status = "Bitte einen synadm-Befehl eingeben."
            return
        if spec.dangerous and not self._confirm(screen, args):
            self.status = "Destruktive Aktion abgebrochen"
            return
        target = self._typed_confirmation_target(args) if spec.dangerous else None
        if target and not self._confirm_typed_target(screen, target):
            self.status = "Zielbestätigung fehlgeschlagen – Aktion abgebrochen"
            return
        self._launch(args)

    def _command_assistant(
        self,
        screen: curses.window,
        spec: Command,
        defaults: dict[str, str] | None = None,
    ) -> list[str] | None:
        fields = fields_for(spec.argv, spec.hint)
        if not fields:
            return []
        total = len(fields)
        defaults = defaults or {}
        values = [defaults.get(field.label, "") for field in fields]
        index = 0
        while index < total:
            field = fields[index]
            value = self._prompt(
                screen,
                f"{spec.title} · {index + 1}/{total}",
                f"{field.label}: {field.hint}",
                initial=values[index],
                secret=field.secret,
            )
            if isinstance(value, WizardBack):
                index = max(0, index - 1)
                continue
            if value is None:
                self.status = "Assistent abgebrochen"
                return None
            if not value.strip() and field.required:
                self.status = f"{field.label} ist erforderlich"
                continue
            values[index] = value
            index += 1

        collected: list[str] = []
        for field, value in zip(fields, values):
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

    @staticmethod
    def _build_create_user_args(values: dict[str, object]) -> list[str]:
        user_id = str(values.get("user_id", "")).strip()
        if not user_id:
            raise ValueError("Die Matrix-ID ist erforderlich")

        args = ["user", "modify", user_id]
        password = str(values.get("password", "")).strip()
        display_name = str(values.get("display_name", "")).strip()
        email = str(values.get("email", "")).strip()
        avatar_url = str(values.get("avatar_url", "")).strip()
        raw_options = str(values.get("raw_options", "")).strip()

        if password:
            args.extend(["--password", password])
        if display_name:
            args.extend(["--display-name", display_name])
        if email:
            args.extend(["--threepid", "email", email])

        admin = str(values.get("admin", "default"))
        if admin == "admin":
            args.append("--admin")
        elif admin == "no_admin":
            args.append("--no-admin")
        elif admin != "default":
            raise ValueError(f"Unbekannte Admin-Auswahl: {admin}")

        user_type = str(values.get("user_type", "regular"))
        if user_type in ("bot", "support"):
            args.extend(["--user-type", user_type])
        elif user_type not in ("regular", "default", ""):
            raise ValueError(f"Unbekannter Benutzertyp: {user_type}")

        if avatar_url:
            args.extend(["--avatar-url", avatar_url])

        locked = str(values.get("locked", "default"))
        if locked == "lock":
            args.append("--lock")
        elif locked == "unlock":
            args.append("--unlock")
        elif locked != "default":
            raise ValueError(f"Unbekannte Sperrauswahl: {locked}")

        if raw_options:
            try:
                args.extend(shlex.split(raw_options))
            except ValueError as error:
                raise ValueError(f"Ungültige Zusatzoptionen: {error}") from error

        if len(args) == 3:
            raise ValueError("Bitte mindestens Passwort, Anzeigename, E-Mail oder eine Option setzen")
        return args

    def _create_user_wizard(self, screen: curses.window) -> None:
        values: dict[str, object] = {
            "user_id": "",
            "password": "",
            "display_name": "",
            "email": "",
            "admin": "default",
            "user_type": "regular",
            "avatar_url": "",
            "locked": "default",
            "raw_options": "",
        }
        step = 0
        total = 9
        while True:
            result: object
            if step == 0:
                result = self._prompt(
                    screen,
                    f"Benutzer anlegen · {step + 1}/{total}",
                    "Matrix-ID (Pflichtfeld), z. B. @alice:example.org",
                    initial=str(values["user_id"]),
                )
                if isinstance(result, str) and not result.strip():
                    self.status = "Die Matrix-ID ist erforderlich"
                    continue
                key = "user_id"
            elif step == 1:
                result = self._prompt(
                    screen,
                    f"Benutzer anlegen · {step + 1}/{total}",
                    "Startpasswort, optional aber für normale Konten empfohlen",
                    initial=str(values["password"]),
                    secret=True,
                )
                key = "password"
            elif step == 2:
                result = self._prompt(
                    screen,
                    f"Benutzer anlegen · {step + 1}/{total}",
                    "Anzeigename, optional – z. B. Alice Beispiel",
                    initial=str(values["display_name"]),
                )
                key = "display_name"
            elif step == 3:
                result = self._prompt(
                    screen,
                    f"Benutzer anlegen · {step + 1}/{total}",
                    "E-Mail-Adresse als ThreePID, optional",
                    initial=str(values["email"]),
                )
                key = "email"
            elif step == 4:
                result = self._select_dialog_option(
                    screen,
                    f"Benutzer anlegen · {step + 1}/{total}",
                    "Administrative Rechte:",
                    (
                        ("Standard: normaler Benutzer", "default"),
                        ("Admin-Rechte setzen", "admin"),
                        ("Explizit kein Admin", "no_admin"),
                    ),
                    str(values["admin"]),
                )
                key = "admin"
            elif step == 5:
                result = self._select_dialog_option(
                    screen,
                    f"Benutzer anlegen · {step + 1}/{total}",
                    "Benutzertyp:",
                    (
                        ("Regular / normaler Benutzer", "regular"),
                        ("Bot", "bot"),
                        ("Support", "support"),
                    ),
                    str(values["user_type"]),
                )
                key = "user_type"
            elif step == 6:
                result = self._select_dialog_option(
                    screen,
                    f"Benutzer anlegen · {step + 1}/{total}",
                    "Sperrstatus beim Anlegen:",
                    (
                        ("Standard: nicht ändern", "default"),
                        ("Konto sperren", "lock"),
                        ("Konto entsperren", "unlock"),
                    ),
                    str(values["locked"]),
                )
                key = "locked"
            elif step == 7:
                result = self._prompt(
                    screen,
                    f"Benutzer anlegen · {step + 1}/{total}",
                    "Avatar-URL, optional – z. B. mxc://example.org/avatar",
                    initial=str(values["avatar_url"]),
                )
                key = "avatar_url"
            elif step == 8:
                result = self._prompt(
                    screen,
                    f"Benutzer anlegen · {step + 1}/{total}",
                    "Erweiterte synadm-Optionen, optional – z. B. --deactivate",
                    initial=str(values["raw_options"]),
                )
                key = "raw_options"
            else:
                try:
                    args = self._build_create_user_args(values)
                except ValueError as error:
                    self.status = str(error)
                    step = 0 if "Matrix-ID" in str(error) else total - 1
                    continue
                if not self._confirm(screen, args):
                    self.status = "Benutzeranlage abgebrochen"
                    return
                self._launch(args)
                return

            if isinstance(result, WizardBack):
                step = max(0, step - 1)
                continue
            if result is None:
                self.status = "Benutzeranlage abgebrochen"
                return
            values[key] = result
            step += 1

    def _open_user_context_menu(self, screen: curses.window) -> None:
        if self.table_view is None:
            return
        user_id = self.table_view.selected_user_id()
        if user_id is None:
            self.status = "Die ausgewählte Tabellenzeile enthält keine Matrix-Benutzer-ID"
            return
        actions = (
            ("Benutzer", "Benutzerdetails"),
            ("Benutzer", "Benutzer ändern"),
            ("Benutzer", "Passwort setzen"),
            ("Benutzer", "Raummitgliedschaften"),
            ("Benutzer", "Benutzer-Medien"),
            ("Benutzer", "Benutzer-Whois"),
            ("Moderation", "Benutzer sperren"),
            ("Moderation", "Benutzer entsperren"),
            ("Moderation", "Alte Geräte prüfen"),
            ("Moderation", "Alte Geräte löschen"),
            ("Moderation", "Shadow-Ban setzen"),
            ("Moderation", "Shadow-Ban aufheben"),
            ("Moderation", "Nachrichten redigieren"),
            ("Benutzer", "Benutzer löschen (GDPR)"),
        )
        options = tuple((title, title) for _section, title in actions)
        selected = self._select_dialog_option(
            screen,
            f"Benutzeraktionen · {user_id}",
            "Aktion für den ausgewählten Benutzer:",
            options,
            options[0][1],
        )
        if not isinstance(selected, str):
            return
        section, title = next((section, title) for section, title in actions if title == selected)
        self._select_command(section, title)
        self._prepare_command(screen, {"Benutzer-ID": user_id})

    def _create_room_wizard(self, screen: curses.window) -> None:
        values: dict[str, object] = {
            "name": "",
            "alias": "",
            "topic": "",
            "visibility": "private",
            "preset": "private_chat",
            "invitees": "",
            "federated": True,
        }
        step = 0
        while True:
            result: object
            if step == 0:
                result = self._prompt(
                    screen,
                    "Raum anlegen · 1/7",
                    "Raumname (Pflichtfeld)",
                    initial=str(values["name"]),
                )
                if isinstance(result, str) and not result.strip():
                    self.status = "Der Raumname ist erforderlich"
                    continue
                key = "name"
            elif step == 1:
                result = self._prompt(
                    screen,
                    "Raum anlegen · 2/7",
                    "Alias lokal, optional – z. B. projekt (ohne # und Server)",
                    initial=str(values["alias"]),
                )
                key = "alias"
            elif step == 2:
                result = self._prompt(
                    screen,
                    "Raum anlegen · 3/7",
                    "Thema/Beschreibung, optional",
                    initial=str(values["topic"]),
                )
                key = "topic"
            elif step == 3:
                result = self._select_dialog_option(
                    screen,
                    "Raum anlegen · 4/7",
                    "Sichtbarkeit im Raumverzeichnis:",
                    (("Privat – nicht im Verzeichnis", "private"), ("Öffentlich – im Verzeichnis", "public")),
                    str(values["visibility"]),
                )
                key = "visibility"
            elif step == 4:
                result = self._select_dialog_option(
                    screen,
                    "Raum anlegen · 5/7",
                    "Vorlage für Beitritt und Berechtigungen:",
                    (
                        ("Privater Raum – nur Einladung", "private_chat"),
                        ("Vertrauensraum – Eingeladene sind Admins", "trusted_private_chat"),
                        ("Öffentlicher Raum – freier Beitritt", "public_chat"),
                    ),
                    str(values["preset"]),
                )
                key = "preset"
            elif step == 5:
                result = self._prompt(
                    screen,
                    "Raum anlegen · 6/7",
                    "Einladungen optional, Matrix-IDs mit Komma trennen",
                    initial=str(values["invitees"]),
                )
                key = "invitees"
            elif step == 6:
                result = self._dialog_yes_no(
                    screen,
                    "Raum anlegen · 7/7",
                    "Darf der Raum mit anderen Matrix-Homeservern föderieren?",
                    default=bool(values["federated"]),
                )
                key = "federated"
            else:
                try:
                    creation = RoomCreation(
                        name=str(values["name"]),
                        alias=str(values["alias"]),
                        topic=str(values["topic"]),
                        visibility=str(values["visibility"]),
                        preset=str(values["preset"]),
                        invitees=parse_invitees(str(values["invitees"])),
                        federated=bool(values["federated"]),
                    )
                    creation.validate()
                except RoomCreationError as error:
                    self.status = str(error)
                    step = 1 if "Alias" in str(error) else 5
                    continue
                confirmed = self._confirm_room_creation(screen, creation)
                if isinstance(confirmed, WizardBack):
                    step = 6
                    continue
                if not confirmed:
                    self.status = "Raumerstellung abgebrochen"
                    return
                self._launch(creation.command())
                return

            if isinstance(result, WizardBack):
                step = max(0, step - 1)
                continue
            if result is None:
                self.status = "Raumerstellung abgebrochen"
                return
            values[key] = result
            step += 1

    def _confirm_room_creation(self, screen: curses.window, creation: RoomCreation) -> bool | WizardBack:
        height, width = screen.getmaxyx()
        box_width = min(width - 4, 88)
        box_height = min(height - 4, 19)
        window = curses.newwin(box_height, box_width, (height - box_height) // 2, (width - box_width) // 2)
        window.keypad(True)
        selected = False
        preview = json.dumps(creation.payload(), ensure_ascii=False, indent=2).splitlines()
        while True:
            window.erase()
            self._draw_dialog_frame(window)
            self._draw_dialog_heading(window, "Raum prüfen und anlegen", curses.A_BOLD | self._color(5))
            self._safe_add(window, 2, 3, "POST /_matrix/client/v3/createRoom", curses.A_BOLD | self._color(1))
            available = max(1, box_height - 7)
            for index, line in enumerate(preview[:available]):
                self._safe_add(window, 3 + index, 3, line[: box_width - 6])
            if len(preview) > available:
                self._safe_add(window, box_height - 4, 3, f"… {len(preview) - available} weitere JSON-Zeilen", curses.A_DIM)
            self._safe_add(window, box_height - 3, 3, "←/→ auswählen · Enter anlegen · Shift+Tab zurück", curses.A_DIM)
            self._draw_yes_no_buttons(window, box_height - 2, box_width, selected)
            window.refresh()
            key = window.getch()
            if key in (10, 13, curses.KEY_ENTER):
                return selected
            if key == curses.KEY_BTAB:
                return WIZARD_BACK
            if key in (curses.KEY_LEFT, curses.KEY_RIGHT, 9, ord("h"), ord("l")):
                selected = not selected
            elif key in (ord("j"), ord("J"), ord("y"), ord("Y")):
                return True
            elif key in (ord("n"), ord("N"), 27):
                return False

    def _launch(self, args: list[str]) -> None:
        if self.running:
            return
        self.running = True
        self.table_view = None
        visible_command = redact_args(self.runner.build_command(args))
        self.output = "$ " + " ".join(shlex.quote(part) for part in visible_command) + "\n\nWird ausgeführt …"
        self.status = "Befehl läuft …"
        self.pending_activity = " ".join(args[:3])
        self.selection.output_offset = 0
        self.show_command_details = False

        def work() -> None:
            structured = "--help" not in args and "-h" not in args
            result = self.runner.run(args, structured=structured)
            verification = self._verification_args(args)
            if result.ok and verification is not None:
                checked = self.runner.run(verification)
                result = self._combined_verification_result(result, checked)
            self.events.put(result)

        threading.Thread(target=work, name="synadm-runner", daemon=True).start()

    def _show_audit(self) -> None:
        path = audit_path()
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            self.status = "Noch kein Audit-Protokoll vorhanden"
            self.output = f"Audit-Datei wird nach der ersten abgeschlossenen Aktion angelegt:\n{path}"
            self.table_view = None
            return
        except OSError as error:
            self.status = "Audit-Protokoll konnte nicht gelesen werden"
            self.output = str(error)
            self.table_view = None
            return
        recent = lines[-200:]
        records: list[dict[str, object]] = []
        for line in recent:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                records.append(record)
        self.output = "\n".join(recent) or "(Audit-Protokoll ist leer)"
        self.table_view = TableView(records) if records else None
        self.selection.output_offset = 0
        self.show_command_details = False
        self.status = f"Audit-Protokoll · {len(recent)} Einträge · {path}"

    def _toggle_demo_mode(self) -> None:
        if self.runner.demo_mode:
            self.runner = self.live_runner
            self.status = "Demo-Modus aus · echte synadm-Verbindung aktiv"
            self.output = "Demo-Modus beendet. Befehle verwenden wieder die konfigurierte synadm-Verbindung."
        else:
            self.live_runner = self.runner
            if self.demo_runner is None:
                self.demo_runner = FakeSynadmRunner()
            self.runner = self.demo_runner
            self.status = "Demo-Modus aktiv · lokales Demo-Backend"
            self.output = "Demo-Modus verwendet lokale JSON-Daten und keinen Synapse-Server."
        self.result = None
        self.table_view = None
        self.selection.output_offset = 0
        self.server_state = "Nicht geprüft"
        self.server_version = "—"
        self._start_server_check()

    @staticmethod
    def _typed_confirmation_target(args: list[str]) -> str | None:
        if len(args) < 2:
            return None
        especially_dangerous = {
            ("user", "deactivate"),
            ("user", "prune-devices"),
            ("user", "redact"),
            ("room", "delete"),
            ("history", "purge"),
            ("media", "delete"),
        }
        if tuple(args[:2]) not in especially_dangerous or "--list-only" in args:
            return None
        if args[0] == "media" and "--media-id" in args:
            position = args.index("--media-id") + 1
            return args[position] if position < len(args) else None
        prefixes = ("@",) if args[0] == "user" else ("!", "#")
        return next((part for part in args[2:] if part.startswith(prefixes)), None)

    def _confirm_typed_target(self, screen: curses.window, target: str) -> bool:
        entered = self._prompt(
            screen,
            "Ziel zur Sicherheit bestätigen",
            f"Bitte exakt {target} eingeben",
        )
        return isinstance(entered, str) and entered == target

    @staticmethod
    def _verification_args(args: list[str]) -> list[str] | None:
        if len(args) < 2:
            return None
        operation = tuple(args[:2])
        user_target = next((part for part in args[2:] if part.startswith("@")), None)
        room_target = next((part for part in args[2:] if part.startswith(("!", "#"))), None)
        if operation == ("user", "prune-devices") and user_target:
            return ["user", "whois", user_target]
        if operation in {
            ("user", "modify"), ("user", "password"), ("user", "deactivate"),
            ("user", "suspend"), ("user", "shadow-ban"),
        } and user_target:
            return ["user", "details", user_target]
        if operation == ("room", "join") and room_target:
            return ["room", "members", room_target]
        if operation == ("room", "make-admin") and room_target:
            return ["room", "state", room_target]
        if operation == ("room", "block") and room_target:
            return ["room", "block-status", room_target]
        return None

    @staticmethod
    def _combined_verification_result(action: Result, verification: Result) -> Result:
        def decoded(value: str) -> object:
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value.strip() or None

        payload = {
            "action": decoded(action.stdout),
            "verification": decoded(verification.stdout),
            "verification_ok": verification.ok,
            "verification_error": verification.stderr.strip() or None,
        }
        return Result(
            action.command,
            action.returncode,
            json.dumps(payload, ensure_ascii=False),
            action.stderr,
            action.duration + verification.duration,
        )

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
                        capture_output=True,
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

    def _configure_synadm(self, screen: curses.window) -> None:
        if not self.runner.available:
            self.status = "synadm wurde nicht gefunden"
            self.output = "Bitte zuerst unter Weitere → synadm installieren/aktualisieren installieren."
            return
        values: dict[str, object] = {
            "path": self.runner.config_file or "~/.config/synadm.yaml",
            "user": "", "token": "", "protocol": "http",
            "base_url": "http://localhost:8008", "admin_path": "/_synapse/admin",
            "matrix_path": "/_matrix", "homeserver": "auto-retrieval",
            "discovery": "well-known", "format": "yaml", "timeout": "30",
            "ssl_verify": True,
        }
        steps = (
            ("path", "Pfad der Konfigurationsdatei"),
            ("user", "Matrix-Admin, z. B. @admin:example.org"),
            ("token", "Admin-Zugriffstoken (verdeckt)"),
            ("protocol", "Verbindungsart"),
            ("base_url", "Synapse-Basis-URL oder absoluter Socket-Pfad"),
            ("admin_path", "Synapse Admin API-Pfad"),
            ("matrix_path", "Matrix API-Pfad"),
            ("homeserver", "Homeserver-Domain oder auto-retrieval"),
            ("discovery", "Homeserver-Erkennung"),
            ("format", "Standard-Ausgabeformat"),
            ("timeout", "HTTP-Timeout in Sekunden"),
            ("ssl_verify", "TLS-Zertifikate prüfen?"),
        )
        index = 0
        while index < len(steps):
            key, hint = steps[index]
            title = f"synadm-Einrichtung · {index + 1}/{len(steps)}"
            if key == "protocol":
                result: object = self._select_dialog_option(
                    screen, title, hint,
                    (("HTTP / HTTPS", "http"), ("Unix-Socket", "unix")),
                    str(values[key]),
                )
            elif key == "discovery":
                result = self._select_dialog_option(
                    screen, title, hint,
                    (("Well-known", "well-known"), ("DNS SRV", "dns")),
                    str(values[key]),
                )
            elif key == "format":
                result = self._select_dialog_option(
                    screen, title, hint,
                    tuple((name.upper(), name) for name in OUTPUT_FORMATS),
                    str(values[key]),
                )
            elif key == "ssl_verify":
                if values["protocol"] == "unix":
                    values[key] = True
                    index += 1
                    continue
                result = self._dialog_yes_no(
                    screen, title,
                    "Bei selbstsignierten Zertifikaten kann Nein erforderlich sein.",
                    default=bool(values[key]),
                )
            else:
                result = self._prompt(
                    screen, title, hint, initial=str(values[key]), secret=key == "token",
                )
            if isinstance(result, WizardBack):
                index = max(0, index - 1)
                continue
            if result is None:
                self.status = "Erstkonfiguration abgebrochen"
                return
            if isinstance(result, str) and not result.strip():
                self.status = "Dieses Feld ist erforderlich"
                continue
            if key == "timeout":
                try:
                    if int(str(result)) < 1:
                        raise ValueError
                except ValueError:
                    self.status = "Bitte eine positive ganze Zahl eingeben"
                    continue
            values[key] = result
            if key == "protocol" and result == "unix" and values["base_url"] == "http://localhost:8008":
                values["base_url"] = "/run/matrix-synapse/synapse.sock"
            elif key == "protocol" and result == "http" and str(values["base_url"]).startswith("/"):
                values["base_url"] = "http://localhost:8008"
            index += 1

        path = Path(str(values["path"])).expanduser()
        config = SynadmConfig(
            user=str(values["user"]), token=str(values["token"]),
            protocol=str(values["protocol"]), base_url=str(values["base_url"]),
            admin_path=str(values["admin_path"]), matrix_path=str(values["matrix_path"]),
            format=str(values["format"]), timeout=int(str(values["timeout"])),
            server_discovery=str(values["discovery"]), homeserver=str(values["homeserver"]),
            ssl_verify=bool(values["ssl_verify"]),
        )
        try:
            config.validate()
        except ValueError as error:
            self.status = "Konfiguration ist ungültig"
            self.output = str(error)
            return
        confirmation = self._confirm_synadm_config(screen, path, config)
        while isinstance(confirmation, WizardBack):
            if config.protocol == "http":
                previous = self._dialog_yes_no(
                    screen, "synadm-Einrichtung · 12/12",
                    "TLS-Zertifikate prüfen?", default=config.ssl_verify,
                )
                if previous is None:
                    self.status = "Erstkonfiguration abgebrochen"
                    return
                if isinstance(previous, WizardBack):
                    continue
                config = replace(config, ssl_verify=bool(previous))
            else:
                previous_timeout = self._prompt(
                    screen, "synadm-Einrichtung · 11/12",
                    "HTTP-Timeout in Sekunden", initial=str(config.timeout),
                )
                if previous_timeout is None:
                    self.status = "Erstkonfiguration abgebrochen"
                    return
                if isinstance(previous_timeout, WizardBack):
                    continue
                try:
                    parsed_timeout = int(previous_timeout)
                    if parsed_timeout < 1:
                        raise ValueError
                except ValueError:
                    self.status = "Bitte eine positive ganze Zahl eingeben"
                    continue
                config = replace(config, timeout=parsed_timeout)
            confirmation = self._confirm_synadm_config(screen, path, config)
        if not confirmation:
            self.status = "Erstkonfiguration abgebrochen"
            return
        backup: Path | None = None
        if path.exists():
            overwrite = self._dialog_yes_no(screen, "Vorhandene Konfiguration", f"{path} sichern und überschreiben?", default=False)
            if not overwrite or isinstance(overwrite, WizardBack):
                self.status = "Vorhandene Konfiguration wurde nicht verändert"
                return
            try:
                backup = backup_synadm_config(path)
            except OSError as error:
                self.status = "Sicherung der Konfiguration fehlgeschlagen"
                self.output = str(error)
                return
        try:
            write_synadm_config(path, config)
        except OSError as error:
            self.status = "Konfiguration konnte nicht gespeichert werden"
            self.output = str(error)
            return
        self.runner.config_file = str(path)
        self.status = "Konfiguration sicher gespeichert · Verbindung wird geprüft"
        backup_line = f"\nSicherung: {backup}" if backup else ""
        self.output = f"Konfiguration: {path}\nDateirechte: 0600{backup_line}\n\n{config.public_summary()}"
        self.selection.output_offset = 0
        self.config_test_pending = True
        self._start_server_check()

    def _csv_import_wizard(self, screen: curses.window) -> None:
        step = 0
        path: str | None = None
        delimiter = ";"
        has_header = True
        data: CsvData | None = None
        mapping: dict[str, int | None] | None = None
        user_id_mode = "preserve"
        homeserver = ""
        while True:
            if step == 0:
                path = self._choose_csv_file(screen)
                if not path:
                    self.status = "CSV-Import abgebrochen"
                    return
                try:
                    detected = inspect_csv(path, has_header=False)
                except CsvImportError as error:
                    self._show_error(str(error))
                    return
                delimiter = detected.delimiter
                step = 1
            elif step == 1:
                chosen = self._choose_delimiter(screen, delimiter)
                if isinstance(chosen, WizardBack):
                    step = 0
                    continue
                if chosen is None:
                    self.status = "CSV-Import abgebrochen"
                    return
                delimiter = chosen
                header_answer = self._ask_yes_no(
                    screen, "CSV-Import · Kopfzeile",
                    "Enthält die erste Zeile Spaltennamen?", default=has_header,
                )
                if isinstance(header_answer, WizardBack):
                    continue
                if header_answer is None:
                    self.status = "CSV-Import abgebrochen"
                    return
                has_header = header_answer
                assert path is not None
                try:
                    data = inspect_csv(path, delimiter, has_header=has_header)
                except CsvImportError as error:
                    self._show_error(str(error))
                    return
                step = 2
            elif step == 2 and data is not None:
                mapped = self._map_csv_columns(screen, data, initial=mapping)
                if isinstance(mapped, WizardBack):
                    step = 1
                    continue
                if mapped is None:
                    self.status = "CSV-Import abgebrochen"
                    return
                mapping = mapped
                step = 3
            elif step == 3 and data is not None and mapping is not None:
                user_id_settings = self._choose_csv_user_id_handling(
                    screen,
                    user_id_mode=user_id_mode,
                    homeserver=homeserver,
                )
                if isinstance(user_id_settings, WizardBack):
                    step = 2
                    continue
                if user_id_settings is None:
                    self.status = "CSV-Import abgebrochen"
                    return
                user_id_mode, homeserver = user_id_settings
                step = 4
            elif step == 4 and data is not None and mapping is not None:
                try:
                    entries = build_entries(data, mapping, user_id_mode=user_id_mode, homeserver=homeserver)
                except CsvImportError as error:
                    self._show_error(str(error))
                    return
                confirmed = self._confirm_csv_import(screen, data, entries, mapping)
                if isinstance(confirmed, WizardBack):
                    step = 3
                    continue
                if not confirmed:
                    self.status = "CSV-Import abgebrochen"
                    return
                self._launch_csv_import(entries, data.path.name)
                return

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
            offset = min(offset, selected)
            if selected >= offset + visible_height:
                offset = selected - visible_height + 1

            screen.erase()
            self._draw_csv_header(screen, 1, "Datei auswählen")
            self._draw_box(screen, 2, 0, height - 4, width, "CSV-Dateien", True)
            self._safe_add(screen, 3, 2, "Verzeichnis:", curses.A_BOLD | self._color(1))
            self._safe_add(screen, 3, 15, str(directory)[: max(1, width - 17)])
            try:
                screen.attron(curses.A_DIM)
                screen.hline(4, 1, curses.ACS_HLINE, width - 2)
                screen.attroff(curses.A_DIM)
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
                if isinstance(manual, WizardBack):
                    continue
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
        audit_error: OSError | None = None
        try:
            append_audit(result.command, result.returncode, result.duration)
        except OSError as error:
            audit_error = error
        body = result.stdout if result.stdout.strip() else result.stderr
        self.table_view = TableView.from_json(body) if result.ok else None
        self.output = pretty_output(body)
        if result.stdout.strip() and result.stderr.strip():
            self.output += "\n\nHinweise:\n" + result.stderr.strip()
        state = "Erfolgreich" if result.ok else f"Fehler (Exit {result.returncode})"
        self.status = f"{state} · {result.duration:.2f} s"
        if audit_error is not None:
            self.status += " · Audit-Protokoll nicht schreibbar"
        label = self.pending_activity or " ".join(result.command[-3:])
        self.activities.insert(0, Activity(datetime.now(timezone.utc).astimezone().strftime("%H:%M:%S"), label, result.ok))
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
            if self.config_test_pending:
                diagnostic = result.stderr.strip() or result.stdout.strip() or "Keine Fehlerdetails verfügbar."
                self.output += "\n\nVERBINDUNGSTEST: FEHLGESCHLAGEN\n" + diagnostic
                self.status = "Konfiguration gespeichert · Verbindungstest fehlgeschlagen"
                self.config_test_pending = False
            return
        self.server_state = "Verbunden"
        try:
            payload = json.loads(result.stdout)
            self.server_version = str(payload.get("server_version", "—"))
        except (json.JSONDecodeError, AttributeError, TypeError):
            self.server_version = "erkannt"
        if self.config_test_pending:
            self.output += f"\n\nVERBINDUNGSTEST: ERFOLGREICH\nSynapse-Version: {self.server_version}"
            self.status = "Konfiguration gespeichert und erfolgreich geprüft"
            self.config_test_pending = False

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
        self.pending_inline_image = None
        height, width = screen.getmaxyx()
        if height < 22 or width < 90:
            self._safe_add(screen, 0, 0, "Terminal zu klein – mindestens 90 × 22 Zeichen benötigt.", curses.A_BOLD)
            self._safe_add(screen, 2, 0, f"Aktuell: {width} × {height}. Mit q beenden.")
            screen.refresh()
            self._sync_inline_image()
            return

        self._safe_add(screen, 0, 0, " " * (width - 1), self._color(8))
        brand = self.brand
        self._safe_add(screen, 0, max(1, (width - len(brand)) // 2), brand, curses.A_BOLD | self._color(8))
        self._safe_add(screen, 0, 2, self.theme.badge, curses.A_BOLD | self._color(8))
        connection = f"● {self.server_state}"
        self._safe_add(screen, 0, width - len(connection) - 2, connection, curses.A_BOLD | self._color(8))
        self._safe_add(screen, 1, 0, "═" * (width - 1), curses.A_BOLD | self._color(1))

        layout = self._panel_layout(height, width)
        assert layout is not None
        output_x = layout.command_x + layout.command_width + 1
        output_width = width - output_x

        self._draw_server_panel(
            screen,
            layout.body_y,
            0,
            layout.left_width,
            layout.server_height,
        )
        self._draw_sections(
            screen, layout.sections_y, 0, layout.left_width, layout.sections_height
        )
        self._draw_quick_actions(
            screen, layout.quick_y, 0, layout.left_width, layout.quick_height
        )
        self._draw_commands(
            screen,
            layout.body_y,
            layout.command_x,
            layout.command_width,
            layout.body_height,
        )

        details_height = max(11, layout.body_height * 2 // 3)
        activity_height = layout.body_height - details_height
        self._draw_output(screen, layout.body_y, output_x, output_width, details_height)
        self._draw_activity(
            screen, layout.body_y + details_height, output_x, output_width, activity_height
        )

        self._safe_add(screen, height - 2, 0, "═" * (width - 1), curses.A_BOLD | self._color(1))
        table_hint = "  Tab Tabelle  Enter Aktionen  v Filter  s Sortierung" if self.table_view is not None else ""
        footer = f"{self.edition.name} · {self.theme.name}  │  Maus/↑/↓ wählen  Enter öffnen{table_hint}  d Demo  ? Hilfe  q Ende"
        self._safe_add(screen, height - 1, 2, footer[: width - 4], curses.A_DIM)
        screen.refresh()
        self._sync_inline_image()

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
        commands = SECTIONS[self.selection.section].commands
        start, end = self._command_viewport(len(commands), self.selection.command, height - 4)
        for row, command in enumerate(commands[start:end]):
            index = start + row
            selected = index == self.selection.command
            active = selected and self.focus == "commands"
            attr = self._color(2) | curses.A_BOLD if active else (self._color(5) if command.dangerous else 0)
            info = command_info(command)
            marker = "! " if command.dangerous else ("+ " if info.writes else "· ")
            self._safe_add(screen, y + 2 + row, x + 2, (marker + command.title)[: width - 4], attr)
        spec = self.current_command
        if spec.hint:
            self._safe_add(screen, y + height - 2, x + 2, ("Eingabe: " + spec.hint)[: width - 8], curses.A_DIM)
        if start:
            self._safe_add(screen, y + 1, x + width - 5, "↑", curses.A_BOLD | self._color(1))
        if end < len(commands):
            self._safe_add(screen, y + height - 2, x + width - 5, "↓", curses.A_BOLD | self._color(1))

    @staticmethod
    def _command_viewport(total: int, selected: int, capacity: int) -> tuple[int, int]:
        """Return a stable scrolling window around the selected command."""
        capacity = max(1, capacity)
        if total <= capacity:
            return 0, total
        start = selected - capacity // 2
        start = max(0, min(start, total - capacity))
        return start, start + capacity

    def _draw_output(self, screen: curses.window, y: int, x: int, width: int, height: int) -> None:
        title = "Details / Ausgabe"
        if self.result:
            title += "  ✓" if self.result.ok else "  ✗"
        self._draw_box(screen, y, x, height, width, title, self.focus == "table")
        if self.show_command_details:
            self._draw_command_details(screen, y, x, width, height)
            return
        if self.result is None and self.output.startswith("Bereit."):
            image_path = self.theme.image_path or theme_image_path(self.theme.key)
            if (
                image_path is not None
                and self.inline_images_supported
                and image_path.is_file()
            ):
                image_rows = max(4, min(10, height - 4))
                image_columns = max(7, min(width - 4, round(image_rows * 1.73)))
                image_x = x + max(2, (width - image_columns) // 2)
                self.pending_inline_image = (image_path, y + 3, image_x + 1, image_rows, image_columns)
                label = self.theme.ready_label
                self._safe_add(
                    screen, min(y + height - 2, y + 3 + image_rows),
                    x + max(2, (width - len(label)) // 2), label[: width - 4],
                    curses.A_BOLD | self._color(1),
                )
                return
            if self._draw_block_theme(screen, y, x, width, height):
                return
            crest_width = max(len(line) for line in self.theme.art)
            crest_x = x + max(2, (width - crest_width) // 2)
            for line_no, line in enumerate(self.theme.art[: max(0, height - 4)]):
                color = self._color(1) if line_no % 3 else self._color(7)
                self._safe_add(screen, y + 2 + line_no, crest_x, line[: width - 4], curses.A_BOLD | color)
            label_y = y + 2 + min(len(self.theme.art), max(0, height - 4))
            label = self.theme.ready_label
            self._safe_add(screen, label_y, x + max(2, (width - len(label)) // 2), label[: width - 4], curses.A_BOLD | self._color(1))
            return
        lines: list[str] = []
        if self.table_view is not None:
            lines = self.table_view.render(max(8, width - 4))
            selected_line = 3 + self.table_view.selected
            visible_height = max(1, height - 3)
            if selected_line < self.selection.output_offset:
                self.selection.output_offset = selected_line
            elif selected_line >= self.selection.output_offset + visible_height:
                self.selection.output_offset = selected_line - visible_height + 1
        else:
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

    def _sync_inline_image(self) -> None:
        if self.pending_inline_image is None:
            self._clear_inline_image()
            return
        path, row, column, rows, columns = self.pending_inline_image
        signature = (path, row, column, rows, columns)
        if signature == self.inline_image_signature:
            return
        try:
            sequence = kitty_render_sequence(path.read_bytes(), row, column, rows, columns)
            write_terminal_sequence(sequence)
        except OSError:
            self.inline_images_supported = False
            self.inline_image_signature = None
            return
        self.inline_image_signature = signature

    def _draw_block_theme(
        self,
        screen: curses.window,
        y: int,
        x: int,
        width: int,
        height: int,
    ) -> bool:
        if not curses.has_colors() or getattr(curses, "COLORS", 0) < 256:
            return False
        rows = load_block_cells(self.theme.key, self.theme.block_path)
        if not rows or len(rows) > height - 4:
            return False
        art_width = len(rows[0])
        start_x = x + max(2, (width - art_width) // 2)
        start_y = y + 2
        for row_index, row in enumerate(rows):
            for column_index, cell in enumerate(row):
                if cell is None:
                    continue
                attr = self._block_color(cell.foreground, cell.background)
                self._safe_add(screen, start_y + row_index, start_x + column_index, cell.character, attr)
        label = self.theme.ready_label
        self._safe_add(
            screen, min(y + height - 2, start_y + len(rows) + 1),
            x + max(2, (width - len(label)) // 2), label[: width - 4],
            curses.A_BOLD | self._color(1),
        )
        return True

    def _block_color(self, foreground: int, background: int) -> int:
        key = (foreground, background)
        pair = self.block_color_pairs.get(key)
        if pair is not None:
            return curses.color_pair(pair)
        pair = 16 + len(self.block_color_pairs)
        if pair >= getattr(curses, "COLOR_PAIRS", 0):
            return curses.A_BOLD | self._color(6)
        try:
            curses.init_pair(pair, foreground, background)
        except curses.error:
            return curses.A_BOLD | self._color(6)
        self.block_color_pairs[key] = pair
        return curses.color_pair(pair)

    def _clear_inline_image(self) -> None:
        if self.inline_image_signature is None:
            return
        try:
            write_terminal_sequence(kitty_delete_sequence())
        except OSError:
            pass
        self.inline_image_signature = None

    def _draw_command_details(self, screen: curses.window, y: int, x: int, width: int, height: int) -> None:
        spec = self.current_command
        info = command_info(spec)
        access = "SCHREIBEND" if info.writes else "LESEND"
        access_attr = self._color(5) if info.writes else self._color(3)
        self._safe_add(screen, y + 2, x + 2, f"ZUGRIFF: {access}", curses.A_BOLD | access_attr)
        lines: list[tuple[str, int]] = []
        for line in textwrap.wrap(info.description, max(1, width - 4)):
            lines.append((line, 0))
        lines.append(("", 0))
        lines.append(("BEISPIEL", curses.A_BOLD | self._color(1)))
        for line in textwrap.wrap(info.example, max(1, width - 4), replace_whitespace=False):
            lines.append((line, curses.A_DIM))
        if spec.dangerous:
            lines.extend((("", 0), ("! Zusätzliche Sicherheitsbestätigung erforderlich", curses.A_BOLD | self._color(4))))
        for index, (line, attr) in enumerate(lines[: max(0, height - 5)]):
            self._safe_add(screen, y + 4 + index, x + 2, line[: width - 4], attr)

    def _draw_server_panel(self, screen: curses.window, y: int, x: int, width: int, height: int) -> None:
        self._draw_box(screen, y, x, height, width, "Server", False)
        state_color = self._color(3) if self.server_state == "Verbunden" else self._color(5)
        self._safe_add(screen, y + 1, x + 2, f"● {self.server_state}"[: width - 4], curses.A_BOLD | state_color)
        available_rows = max(0, height - 3)
        lines: list[tuple[str, int]] = []
        lines.extend((line, curses.A_NORMAL) for line in self._wrap_panel_value("Synapse", self.server_version, width - 4))
        lines.extend((line, self._status_color()) for line in self._wrap_panel_value("Status", self.status, width - 4))
        for index, (line, attr) in enumerate(lines[:available_rows]):
            self._safe_add(screen, y + 2 + index, x + 2, line, attr)

    @staticmethod
    def _wrap_panel_value(label: str, value: str, width: int) -> list[str]:
        """Wrap a labelled panel value and align continuation lines."""
        if width < 1:
            return []
        prefix = f"{label}: "
        return textwrap.wrap(
            prefix + (value.strip() or "—"),
            width=width,
            subsequent_indent=" " * min(len(prefix), max(0, width - 1)),
            break_long_words=True,
            break_on_hyphens=True,
            replace_whitespace=True,
        ) or [prefix[:width]]

    def _draw_quick_actions(self, screen: curses.window, y: int, x: int, width: int, height: int) -> None:
        if height < 3:
            return
        self._draw_box(screen, y, x, height, width, "Schnellaktionen", False)
        actions = (
            ("n", "Benutzer anlegen"),
            ("i", "CSV importieren"),
            ("/", "Benutzer suchen"),
            ("x", "Benutzer löschen"),
            ("a", "Raum anlegen"),
        )
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
        attr = self._color(1) | curses.A_BOLD if active else self._color(7) | curses.A_BOLD
        self._draw_frame(screen, y, x, height, width, attr)
        rendered_title = f"[ {title.upper()} ]"
        title_x = x + max(2, (width - len(rendered_title)) // 2)
        self._safe_add(screen, y, title_x, rendered_title[: width - 4], curses.A_BOLD | self._color(1))

    @staticmethod
    def _draw_frame(
        window: curses.window,
        y: int,
        x: int,
        height: int,
        width: int,
        attr: int,
    ) -> None:
        """Draw a double-line frame, with an ACS fallback for limited terminals."""
        if height < 2 or width < 4:
            return
        try:
            window.addstr(y, x, "╔" + "═" * (width - 2) + "╗", attr)
            for row in range(y + 1, y + height - 1):
                window.addstr(row, x, "║", attr)
                window.addstr(row, x + width - 1, "║", attr)
        except curses.error:
            try:
                window.attron(attr)
                window.hline(y, x + 1, curses.ACS_HLINE, width - 2)
                window.hline(y + height - 1, x + 1, curses.ACS_HLINE, width - 2)
                window.vline(y + 1, x, curses.ACS_VLINE, height - 2)
                window.vline(y + 1, x + width - 1, curses.ACS_VLINE, height - 2)
                window.attroff(attr)
                window.addch(y, x, curses.ACS_ULCORNER, attr)
                window.addch(y, x + width - 1, curses.ACS_URCORNER, attr)
                window.addch(y + height - 1, x, curses.ACS_LLCORNER, attr)
                window.addch(y + height - 1, x + width - 1, curses.ACS_LRCORNER, attr)
            except curses.error:
                pass
            return
        # curses reports ERR after successfully painting the bottom-right cell
        # of a subwindow. Keep the Unicode frame instead of replacing it.
        try:
            window.addstr(y + height - 1, x, "╚" + "═" * (width - 2) + "╝", attr)
        except curses.error:
            pass

    def _draw_dialog_frame(self, window: curses.window) -> None:
        height, width = window.getmaxyx()
        self._draw_frame(window, 0, 0, height, width, curses.A_BOLD | self._color(1))

    def _draw_dialog_heading(self, window: curses.window, title: str, attr: int) -> None:
        _height, width = window.getmaxyx()
        rendered = f"[ {title.upper()} ]"
        self._safe_add(window, 1, max(2, (width - len(rendered)) // 2), rendered[: width - 4], attr)

    def _choose_theme(self, screen: curses.window) -> None:
        original = self.theme
        selected = next((index for index, theme in enumerate(self.available_themes) if theme.key == original.key), 0)
        height, width = screen.getmaxyx()
        box_width = min(width - 4, 64)
        box_height = 11
        window = curses.newwin(box_height, box_width, (height - box_height) // 2, (width - box_width) // 2)
        window.keypad(True)
        while True:
            window.erase()
            self._draw_dialog_frame(window)
            self._draw_dialog_heading(window, "Thema auswählen", curses.A_BOLD | self._color(1))
            self._safe_add(window, 2, 3, "Farben mit ↑/↓ live ansehen:", curses.A_DIM)
            for index, theme in enumerate(self.available_themes):
                active = index == selected
                marker = "▶" if active else " "
                attr = curses.A_BOLD | self._color(2) if active else curses.A_NORMAL
                self._safe_add(window, 4 + index, 4, f"{marker} {theme.name}"[: box_width - 8], attr)
            self._safe_add(window, box_height - 2, 3, "Enter speichern · Esc zurück · t öffnet die Auswahl", curses.A_DIM)
            window.refresh()
            key = window.getch()
            if key in (curses.KEY_UP, ord("k")):
                selected = (selected - 1) % len(self.available_themes)
                self.theme = self.available_themes[selected]
                self._init_colors()
            elif key in (curses.KEY_DOWN, ord("j")):
                selected = (selected + 1) % len(self.available_themes)
                self.theme = self.available_themes[selected]
                self._init_colors()
            elif key in (10, 13, curses.KEY_ENTER):
                self.theme = self.available_themes[selected]
                saved = self._save_theme(self.theme, self.edition)
                self.status = f"Thema aktiv: {self.theme.name}"
                if not saved:
                    self.status += " (konnte nicht gespeichert werden)"
                return
            elif key == 27:
                self.theme = original
                self._init_colors()
                self.status = "Themenauswahl abgebrochen"
                return

    def _show_keyboard_help(self, screen: curses.window) -> None:
        height, width = screen.getmaxyx()
        box_width = min(width - 4, 78)
        box_height = 18
        window = curses.newwin(box_height, box_width, (height - box_height) // 2, (width - box_width) // 2)
        window.keypad(True)
        entries = (
            ("↑/↓ · j/k", "Auswahl bewegen"),
            ("Enter · →", "Bereich öffnen / Aktion starten"),
            ("← · Esc", "Zur Bereichsauswahl / Dialog abbrechen"),
            ("Shift+Tab", "Im Assistenten einen Schritt zurück"),
            ("f", "Befehle über alle Bereiche filtern"),
            ("c", "synadm-Konfigurationsassistent"),
            ("t", "Thema auswählen"),
            ("d", "Demo-Modus ein-/ausschalten"),
            ("n · i · / · x", "Benutzer neu · CSV · Suche · Löschen"),
            ("a", "Raum anlegen"),
            ("v · s", "Tabelle filtern · sortieren"),
            ("Tab/→ · Enter", "Tabelle fokussieren · Benutzeraktionen"),
            ("PgUp/PgDn", "Ausgabe scrollen"),
            ("q", "Programm beenden"),
        )
        window.erase()
        self._draw_dialog_frame(window)
        self._draw_dialog_heading(window, "Tastaturhilfe", curses.A_BOLD | self._color(1))
        for index, (keys, meaning) in enumerate(entries):
            self._safe_add(window, 3 + index, 4, f"{keys:<16}", curses.A_BOLD | self._color(1))
            self._safe_add(window, 3 + index, 22, meaning[: box_width - 25])
        self._safe_add(window, box_height - 2, 4, "Beliebige Taste schließt die Hilfe", curses.A_DIM)
        window.refresh()
        window.getch()

    def _command_palette(self, screen: curses.window) -> None:
        height, width = screen.getmaxyx()
        box_width = min(width - 4, 86)
        box_height = min(height - 4, 20)
        window = curses.newwin(box_height, box_width, (height - box_height) // 2, (width - box_width) // 2)
        window.keypad(True)
        query: list[str] = []
        selected = 0
        while True:
            needle = "".join(query).casefold()
            matches = [
                (section_index, command_index, section.title, command)
                for section_index, section in enumerate(SECTIONS)
                for command_index, command in enumerate(section.commands)
                if not needle or needle in f"{section.title} {command.title} {command.hint}".casefold()
            ]
            selected = min(selected, max(0, len(matches) - 1))
            window.erase()
            self._draw_dialog_frame(window)
            self._draw_dialog_heading(window, "Befehlsfilter", curses.A_BOLD | self._color(1))
            self._safe_add(window, 2, 3, "Suche: " + "".join(query), curses.A_BOLD)
            max_rows = box_height - 6
            offset = max(0, selected - max_rows + 1)
            for row, (_si, _ci, section_title, command) in enumerate(matches[offset : offset + max_rows]):
                absolute = offset + row
                info = command_info(command)
                mode = "S" if info.writes else "L"
                text = f"[{mode}] {section_title:<15} {command.title}"
                attr = curses.A_BOLD | self._color(2) if absolute == selected else curses.A_NORMAL
                self._safe_add(window, 4 + row, 3, text[: box_width - 6], attr)
            if not matches:
                self._safe_add(window, 5, 3, "Keine passenden Befehle", self._color(5))
            self._safe_add(window, box_height - 2, 3, "Tippen · ↑/↓ wählen · Enter öffnen · Esc abbrechen", curses.A_DIM)
            window.refresh()
            key = window.get_wch()
            if key in ("\n", "\r", curses.KEY_ENTER) and matches:
                section_index, command_index, _section, _command = matches[selected]
                self.selection.section = section_index
                self.selection.command = command_index
                self.focus = "commands"
                self.show_command_details = True
                self.status = "Befehl aus Filter ausgewählt"
                return
            if key in (curses.KEY_UP, "\x10") and matches:
                selected = (selected - 1) % len(matches)
            elif key in (curses.KEY_DOWN, "\x0e") and matches:
                selected = (selected + 1) % len(matches)
            elif key in (curses.KEY_BACKSPACE, "\b", "\x7f"):
                if query:
                    query.pop()
                    selected = 0
            elif key == "\x1b":
                return
            elif isinstance(key, str) and key.isprintable():
                query.append(key)
                selected = 0

    def _select_dialog_option(
        self,
        screen: curses.window,
        title: str,
        prompt: str,
        options: tuple[tuple[str, str], ...],
        current: str,
    ) -> str | None | WizardBack:
        if not options:
            return None
        selected = next((index for index, (_label, value) in enumerate(options) if value == current), 0)
        height, width = screen.getmaxyx()
        box_width = min(width - 4, 64)
        box_height = min(height - 4, max(9, min(18, len(options) + 7)))
        visible_count = max(1, box_height - 7)
        window = curses.newwin(box_height, box_width, (height - box_height) // 2, (width - box_width) // 2)
        window.keypad(True)
        while True:
            window.erase()
            self._draw_dialog_frame(window)
            self._draw_dialog_heading(window, title, curses.A_BOLD | self._color(1))
            self._safe_add(window, 2, 3, prompt[: box_width - 6], curses.A_DIM)
            start = max(0, min(selected - visible_count // 2, len(options) - visible_count))
            for row, (label, _value) in enumerate(options[start : start + visible_count]):
                index = start + row
                active = index == selected
                marker = "▶" if active else " "
                attr = curses.A_BOLD | self._color(2) if active else curses.A_NORMAL
                self._safe_add(window, 4 + row, 4, f"{marker} {label}"[: box_width - 8], attr)
            if start:
                self._safe_add(window, 3, box_width - 5, "↑", curses.A_BOLD | self._color(1))
            if start + visible_count < len(options):
                self._safe_add(window, box_height - 3, box_width - 5, "↓", curses.A_BOLD | self._color(1))
            self._safe_add(window, box_height - 2, 3, "↑/↓ auswählen · Enter übernehmen · Esc abbrechen", curses.A_DIM)
            window.refresh()
            key = window.getch()
            if key in (curses.KEY_UP, ord("k")):
                selected = (selected - 1) % len(options)
            elif key in (curses.KEY_DOWN, ord("j")):
                selected = (selected + 1) % len(options)
            elif key in (10, 13, curses.KEY_ENTER):
                return options[selected][1]
            elif key == curses.KEY_BTAB:
                return WIZARD_BACK
            elif key == 27:
                return None

    def _dialog_yes_no(
        self,
        screen: curses.window,
        title: str,
        question: str,
        *,
        default: bool,
    ) -> bool | None | WizardBack:
        height, width = screen.getmaxyx()
        box_width = min(width - 4, 76)
        box_height = 9
        window = curses.newwin(box_height, box_width, (height - box_height) // 2, (width - box_width) // 2)
        window.keypad(True)
        selected = default
        lines = textwrap.wrap(question, max(10, box_width - 6))[:2]
        while True:
            window.erase()
            self._draw_dialog_frame(window)
            self._draw_dialog_heading(window, title, curses.A_BOLD | self._color(1))
            for index, line in enumerate(lines):
                self._safe_add(window, 3 + index, 3, line)
            self._safe_add(window, 6, 3, "←/→ auswählen · Enter bestätigen · Esc abbrechen", curses.A_DIM)
            self._draw_yes_no_buttons(window, 7, box_width, selected)
            window.refresh()
            key = window.getch()
            if key in (10, 13, curses.KEY_ENTER):
                return selected
            if key == curses.KEY_BTAB:
                return WIZARD_BACK
            if key in (curses.KEY_LEFT, curses.KEY_RIGHT, 9, ord("h"), ord("l")):
                selected = not selected
            elif key in (ord("j"), ord("J"), ord("y"), ord("Y")):
                return True
            elif key in (ord("n"), ord("N")):
                return False
            elif key == 27:
                return None

    def _confirm_synadm_config(
        self,
        screen: curses.window,
        path: Path,
        config: SynadmConfig,
    ) -> bool | WizardBack:
        height, width = screen.getmaxyx()
        box_width = min(width - 4, 82)
        box_height = 16
        window = curses.newwin(box_height, box_width, (height - box_height) // 2, (width - box_width) // 2)
        window.keypad(True)
        selected = False
        summary = [f"Datei:       {path}", *config.public_summary().splitlines()]
        while True:
            window.erase()
            self._draw_dialog_frame(window)
            self._draw_dialog_heading(window, "Konfiguration prüfen", curses.A_BOLD | self._color(1))
            for index, line in enumerate(summary[:9]):
                self._safe_add(window, 3 + index, 3, line[: box_width - 6])
            self._safe_add(window, 13, 3, "Token bleibt verdeckt · ←/→ auswählen · Enter speichern", curses.A_DIM)
            self._draw_yes_no_buttons(window, 14, box_width, selected)
            window.refresh()
            key = window.getch()
            if key in (10, 13, curses.KEY_ENTER):
                return selected
            if key == curses.KEY_BTAB:
                return WIZARD_BACK
            if key in (curses.KEY_LEFT, curses.KEY_RIGHT, 9, ord("h"), ord("l")):
                selected = not selected
            elif key in (ord("j"), ord("J"), ord("y"), ord("Y")):
                return True
            elif key in (ord("n"), ord("N"), 27):
                return False

    def _draw_csv_header(self, screen: curses.window, step: int, title: str) -> None:
        _height, width = screen.getmaxyx()
        brand = self.compact_brand
        self._safe_add(screen, 0, 1, brand, curses.A_BOLD | self._color(1))
        self._safe_add(screen, 0, len(brand) + 4, f"CSV-Import · {title}", curses.A_BOLD)
        steps = ((1, "Datei"), (2, "Format"), (3, "Zuordnung"), (4, "Domain"), (5, "Prüfen"))
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
            self._safe_add(screen, 1, 0, "═" * (width - 1), curses.A_BOLD | self._color(1))
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
    ) -> str | None | WizardBack:
        height, width = screen.getmaxyx()
        box_width = min(width - 4, 76)
        box_height = 7
        y, x = (height - box_height) // 2, (width - box_width) // 2
        window = curses.newwin(box_height, box_width, y, x)
        window.keypad(True)
        value: list[str] = list(initial)
        cursor = len(value)
        offset = 0
        field_width = box_width - 5
        curses.curs_set(1)
        try:
            while True:
                window.erase()
                self._draw_dialog_frame(window)
                self._draw_dialog_heading(window, title, curses.A_BOLD | self._color(1))
                self._safe_add(window, 2, 2, hint[: box_width - 4], curses.A_DIM)
                shown = "".join(value)
                display = "•" * len(shown) if secret else shown
                if cursor < offset:
                    offset = cursor
                elif cursor > offset + field_width:
                    offset = cursor - field_width
                visible = display[offset : offset + field_width]
                self._safe_add(window, 4, 2, visible)
                self._safe_add(window, 5, 2, "←/→ Cursor · Enter weiter · Shift+Tab zurück · Esc abbrechen", curses.A_DIM)
                window.move(4, min(box_width - 3, 2 + cursor - offset))
                window.refresh()
                key = window.get_wch()
                if key in ("\n", "\r", curses.KEY_ENTER):
                    return shown
                if key == "\x1b":
                    return None
                if key == curses.KEY_BTAB:
                    return WIZARD_BACK
                if key in (curses.KEY_LEFT, "\x02"):
                    cursor = max(0, cursor - 1)
                elif key in (curses.KEY_RIGHT, "\x06"):
                    cursor = min(len(value), cursor + 1)
                elif key == curses.KEY_HOME:
                    cursor = 0
                elif key == curses.KEY_END:
                    cursor = len(value)
                elif key in (curses.KEY_BACKSPACE, "\b", "\x7f"):
                    if cursor > 0:
                        value.pop(cursor - 1)
                        cursor -= 1
                    elif not value:
                        return WIZARD_BACK
                elif key == curses.KEY_DC:
                    if cursor < len(value):
                        value.pop(cursor)
                elif isinstance(key, str) and key.isprintable():
                    value.insert(cursor, key)
                    cursor += 1
        finally:
            curses.curs_set(0)

    def _choose_delimiter(self, screen: curses.window, detected: str) -> str | None | WizardBack:
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
            self._draw_dialog_frame(window)
            self._draw_dialog_heading(window, "CSV-Import · 2/5 · Trennzeichen", curses.A_BOLD | self._color(1))
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
            elif key == curses.KEY_BTAB:
                return WIZARD_BACK
            elif key == 27:
                if opened:
                    opened = False
                else:
                    return None

    def _choose_csv_user_id_handling(
        self,
        screen: curses.window,
        *,
        user_id_mode: str,
        homeserver: str,
    ) -> tuple[str, str] | None | WizardBack:
        selected_mode = self._select_dialog_option(
            screen,
            "CSV-Import · 4/5 · Matrix-Domain",
            "Wie sollen Benutzer-IDs aus der CSV behandelt werden?",
            (
                ("Unverändert übernehmen", "preserve"),
                ("Homeserver ergänzen, wenn Domain fehlt", "append_missing"),
                ("Homeserver immer setzen/ersetzen", "replace"),
            ),
            user_id_mode,
        )
        if isinstance(selected_mode, WizardBack):
            return WIZARD_BACK
        if selected_mode is None:
            return None
        if selected_mode == "preserve":
            return selected_mode, ""

        while True:
            result = self._prompt(
                screen,
                "CSV-Import · 4/5 · Homeserver",
                "Matrix-Homeserver-Domain, z. B. matrix.example.org – nicht die API-URL",
                initial=homeserver,
            )
            if isinstance(result, WizardBack):
                return WIZARD_BACK
            if result is None:
                return None
            try:
                normalized = normalize_homeserver(result)
            except CsvImportError as error:
                self.status = str(error)
                continue
            if not normalized:
                self.status = "Bitte die Matrix-Homeserver-Domain angeben"
                continue
            return selected_mode, normalized

    def _ask_yes_no(
        self,
        screen: curses.window,
        title: str,
        question: str,
        *,
        default: bool = False,
    ) -> bool | None | WizardBack:
        height, width = screen.getmaxyx()
        self._draw_csv_backdrop(screen, 2, "Format festlegen", "CSV-Format")
        box_width = min(width - 4, 70)
        window = curses.newwin(7, box_width, (height - 7) // 2, (width - box_width) // 2)
        window.keypad(True)
        selected = default
        while True:
            window.erase()
            self._draw_dialog_frame(window)
            self._draw_dialog_heading(window, title, curses.A_BOLD | self._color(1))
            self._safe_add(window, 3, 2, question[: box_width - 4])
            self._safe_add(window, 4, 2, "←/→ auswählen · Enter bestätigen · Esc abbrechen", curses.A_DIM)
            self._draw_yes_no_buttons(window, 5, box_width, selected)
            window.refresh()
            key = window.getch()
            if key in (10, 13, curses.KEY_ENTER):
                return selected
            if key == curses.KEY_BTAB:
                return WIZARD_BACK
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

    def _map_csv_columns(
        self,
        screen: curses.window,
        data: CsvData,
        *,
        initial: dict[str, int | None] | None = None,
    ) -> dict[str, int | None] | None | WizardBack:
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
        mapping: dict[str, int | None] = dict(initial or {})
        for field in FIELDS:
            if field.key not in mapping:
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
            if key == curses.KEY_BTAB:
                return WIZARD_BACK
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
    ) -> bool | WizardBack:
        height, width = screen.getmaxyx()
        self._draw_csv_backdrop(screen, 4, "Import prüfen", "Zusammenfassung")
        box_height = min(height - 2, 16)
        box_width = min(width - 4, 82)
        window = curses.newwin(box_height, box_width, (height - box_height) // 2, (width - box_width) // 2)
        window.keypad(True)
        selected = False
        while True:
            window.erase()
            self._draw_dialog_frame(window)
            self._draw_dialog_heading(window, "CSV-Import · 5/5 · Vorschau", curses.A_BOLD | self._color(5))
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
            if key == curses.KEY_BTAB:
                return WIZARD_BACK
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
            self._draw_dialog_frame(window)
            self._draw_dialog_heading(window, "Destruktive Aktion", curses.A_BOLD | self._color(4))
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
            self._draw_dialog_frame(window)
            self._draw_dialog_heading(window, "Paketverwaltung", curses.A_BOLD | self._color(5))
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
