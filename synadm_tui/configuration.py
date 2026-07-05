"""Secure creation of synadm configuration files."""

from __future__ import annotations

import json
import os
import secrets
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlsplit
from datetime import datetime


OUTPUT_FORMATS = ("yaml", "json", "minified", "human", "pprint")
DISCOVERY_MODES = ("well-known", "dns")


@dataclass(frozen=True, slots=True)
class SynadmConfig:
    user: str
    token: str
    protocol: str
    base_url: str
    admin_path: str = "/_synapse/admin"
    matrix_path: str = "/_matrix"
    format: str = "yaml"
    timeout: int = 30
    server_discovery: str = "well-known"
    homeserver: str = "auto-retrieval"
    ssl_verify: bool = True

    def validate(self) -> None:
        if not self.user.strip():
            raise ValueError("Der Admin-Benutzer darf nicht leer sein.")
        if not self.token.strip():
            raise ValueError("Der Zugriffstoken darf nicht leer sein.")
        if self.protocol not in ("http", "unix"):
            raise ValueError("Das Protokoll muss http oder unix sein.")
        if self.protocol == "http":
            parsed = urlsplit(self.base_url)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise ValueError("Die Basis-URL muss mit http:// oder https:// beginnen.")
        elif not Path(self.base_url).is_absolute():
            raise ValueError("Der Unix-Socket muss als absoluter Pfad angegeben werden.")
        if not self.admin_path.startswith("/") or not self.matrix_path.startswith("/"):
            raise ValueError("Die API-Pfade müssen mit / beginnen.")
        if self.format not in OUTPUT_FORMATS:
            raise ValueError("Unbekanntes Ausgabeformat.")
        if self.timeout < 1:
            raise ValueError("Der Timeout muss mindestens eine Sekunde betragen.")
        if self.server_discovery not in DISCOVERY_MODES:
            raise ValueError("Unbekannte Homeserver-Erkennung.")
        if not self.homeserver.strip():
            raise ValueError("Der Homeserver darf nicht leer sein.")

    def public_summary(self) -> str:
        tls = "Ja" if self.ssl_verify else "Nein"
        return (
            f"Admin:       {self.user}\n"
            f"Verbindung:  {self.protocol} · {self.base_url}\n"
            f"Homeserver:  {self.homeserver}\n"
            f"TLS prüfen:  {tls}\n"
            f"Ausgabe:     {self.format}\n"
            f"Timeout:     {self.timeout} s\n"
            "Token:       ••••••••"
        )


def write_synadm_config(path: Path, config: SynadmConfig) -> None:
    """Atomically write JSON (valid YAML) with owner-only permissions."""
    config.validate()
    target = path.expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(temporary, flags, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(asdict(config), handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, target)
        os.chmod(target, 0o600)
    except BaseException:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise


def backup_synadm_config(path: Path) -> Path:
    """Create an owner-only timestamped backup next to an existing config."""
    source = path.expanduser()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = source.with_name(f"{source.name}.bak-{stamp}")
    counter = 1
    while backup.exists():
        backup = source.with_name(f"{source.name}.bak-{stamp}-{counter}")
        counter += 1
    shutil.copy2(source, backup)
    os.chmod(backup, 0o600)
    return backup
