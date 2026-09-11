#!/usr/bin/env python3
# ruff: noqa: I001
"""Executable wrapper for the synadm-tui local demo backend."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from synadm_tui.fake_synadm import main


if __name__ == "__main__":
    raise SystemExit(main())
