"""Safe subprocess integration for the synadm command line client."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Result:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    duration: float

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def text(self) -> str:
        return self.stdout.strip() or self.stderr.strip() or "(keine Ausgabe)"


class SynadmRunner:
    def __init__(
        self,
        executable: str = "synadm",
        config_file: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.executable = executable
        self.config_file = config_file
        self.timeout = timeout

    @property
    def available(self) -> bool:
        if os.sep in self.executable:
            return Path(self.executable).is_file() and os.access(self.executable, os.X_OK)
        return shutil.which(self.executable) is not None

    @property
    def demo_mode(self) -> bool:
        return False

    def build_command(self, args: Sequence[str], *, structured: bool = True) -> list[str]:
        command = [self.executable, "--batch"]
        if structured and "--help" not in args and "-h" not in args and "config" not in args:
            command += ["--output", "json"]
        if self.config_file:
            command += ["--config-file", self.config_file]
        command.extend(args)
        return command

    def run(self, args: Sequence[str], *, structured: bool = True) -> Result:
        command = self.build_command(args, structured=structured)
        started = time.monotonic()
        try:
            process = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
                env=_subprocess_env(),
            )
            return Result(
                tuple(command), process.returncode, process.stdout, process.stderr,
                time.monotonic() - started,
            )
        except FileNotFoundError:
            return Result(tuple(command), 127, "", f"{self.executable!r} wurde nicht gefunden.", time.monotonic() - started)
        except subprocess.TimeoutExpired as error:
            stdout = _decode(error.stdout)
            stderr = _decode(error.stderr)
            message = f"Zeitlimit von {self.timeout:g} Sekunden überschritten."
            return Result(tuple(command), 124, stdout, stderr + ("\n" if stderr else "") + message, time.monotonic() - started)


def pretty_output(text: str) -> str:
    """Pretty-print JSON while leaving human-readable output untouched."""
    stripped = text.strip()
    if not stripped:
        return "(keine Ausgabe)"
    try:
        return json.dumps(json.loads(stripped), ensure_ascii=False, indent=2)
    except (json.JSONDecodeError, TypeError):
        return stripped


def _subprocess_env() -> dict[str, str]:
    """Return a clean environment for launching external tools.

    PyInstaller one-file binaries adjust the dynamic library path for their
    embedded runtime. If a separately installed Python CLI like synadm inherits
    that path, it can load the wrong libpython/OpenSSL libraries and fail with
    errors such as a missing ssl module. PyInstaller stores the previous value
    in LD_LIBRARY_PATH_ORIG; restore that value or remove LD_LIBRARY_PATH.
    """

    environment = dict(os.environ)
    original_library_path = environment.get("LD_LIBRARY_PATH_ORIG")
    if original_library_path:
        environment["LD_LIBRARY_PATH"] = original_library_path
    else:
        environment.pop("LD_LIBRARY_PATH", None)
    environment["NO_COLOR"] = "1"
    return environment


def _decode(value: bytes | str | None) -> str:
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value or ""
