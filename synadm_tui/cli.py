"""Command line entry point."""

from __future__ import annotations

import argparse

from . import __version__
from .app import App, Theme
from .edition import STANDARD_EDITION, Edition
from .fake_synadm import FakeSynadmRunner
from .runner import SynadmRunner


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Terminal-Oberfläche für synadm")
    result.add_argument("--synadm", default="synadm", metavar="PFAD", help="synadm-Programm (Standard: synadm)")
    result.add_argument("--config-file", metavar="PFAD", help="alternative synadm-Konfigurationsdatei")
    result.add_argument("--timeout", type=float, default=60.0, metavar="SEK", help="Zeitlimit pro Aufruf")
    result.add_argument("--demo", action="store_true", help="lokales Demo-Backend ohne Synapse-Server verwenden")
    result.add_argument("--demo-state", metavar="PFAD", help="JSON-Datei für den lokalen Demo-Zustand")
    result.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return result


def main(
    argv: list[str] | None = None,
    *,
    edition: Edition = STANDARD_EDITION,
    extra_themes: tuple[Theme, ...] = (),
) -> int:
    args = parser().parse_args(argv)
    if args.timeout <= 0:
        parser().error("--timeout muss größer als 0 sein")
    runner: SynadmRunner
    if args.demo:
        runner = FakeSynadmRunner(args.demo_state, args.timeout)
    else:
        runner = SynadmRunner(args.synadm, args.config_file, args.timeout)
    try:
        App(runner, edition, extra_themes).run()
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
