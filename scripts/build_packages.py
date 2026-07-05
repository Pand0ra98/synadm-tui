#!/usr/bin/env python3
"""Build installable Debian and RPM packages from the native executables."""

from __future__ import annotations

import argparse
import math
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
OUTPUT = DIST / "packages"
HOMEPAGE = "https://git.blackwall.ipv64.de/pan/synadm-tui"
DEFAULT_RPM_SIGNING_HOME = Path.home() / ".local" / "share" / "synadm-tui" / "rpm-signing"


@dataclass(frozen=True)
class Edition:
    package: str
    executable: str
    summary: str
    description: str


EDITIONS = (
    Edition(
        "synadm-tui",
        "synadm-tui",
        "Terminal-Oberfläche für die Matrix-Synapse-Administration",
        "Eine tastaturorientierte, von LazyDocker inspirierte Oberfläche für synadm.",
    ),
)


def project_version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


def architecture() -> tuple[str, str]:
    machine = platform.machine().lower()
    mappings = {
        "x86_64": ("amd64", "x86_64"),
        "amd64": ("amd64", "x86_64"),
        "aarch64": ("arm64", "aarch64"),
        "arm64": ("arm64", "aarch64"),
    }
    try:
        return mappings[machine]
    except KeyError as error:
        raise SystemExit(f"Nicht unterstützte Architektur: {machine}") from error


def require_native_files() -> None:
    missing = [edition.executable for edition in EDITIONS if not (DIST / edition.executable).is_file()]
    if missing:
        names = ", ".join(missing)
        raise SystemExit(f"Native Dateien fehlen ({names}); zuerst scripts/build_native.py ausführen.")
    expected = project_version()
    for edition in EDITIONS:
        result = subprocess.run(
            [str(DIST / edition.executable), "--version"],
            check=True,
            capture_output=True,
            text=True,
        )
        if not result.stdout.strip().endswith(expected):
            raise SystemExit(
                f"{edition.executable} passt nicht zu Version {expected}; "
                "scripts/build_native.py erneut ausführen."
            )


def write_debian_control(stage: Path, edition: Edition, version: str, arch: str) -> None:
    size_kib = math.ceil((DIST / edition.executable).stat().st_size / 1024)
    control = (
        f"Package: {edition.package}\n"
        f"Version: {version}\n"
        f"Section: admin\n"
        f"Priority: optional\n"
        f"Architecture: {arch}\n"
        f"Maintainer: synadm-tui contributors\n"
        f"Installed-Size: {size_kib}\n"
        f"Depends: libc6 (>= 2.34), zlib1g\n"
        f"Homepage: {HOMEPAGE}\n"
        f"Description: {edition.summary}\n"
        f" {edition.description}\n"
    )
    control_dir = stage / "DEBIAN"
    control_dir.mkdir(parents=True)
    (control_dir / "control").write_text(control, encoding="utf-8")


def populate_payload(stage: Path, edition: Edition) -> None:
    binary_dir = stage / "usr" / "bin"
    doc_dir = stage / "usr" / "share" / "doc" / edition.package
    binary_dir.mkdir(parents=True)
    doc_dir.mkdir(parents=True)
    shutil.copy2(DIST / edition.executable, binary_dir / edition.executable)
    (binary_dir / edition.executable).chmod(0o755)
    shutil.copy2(ROOT / "README.md", doc_dir / "README.md")
    shutil.copy2(ROOT / "LICENSE", doc_dir / "copyright")


def normalize_permissions(stage: Path, executable: str) -> None:
    stage.chmod(0o755)
    for path in stage.rglob("*"):
        path.chmod(0o755 if path.is_dir() else 0o644)
    (stage / "usr" / "bin" / executable).chmod(0o755)


def build_deb(version: str, deb_arch: str) -> list[Path]:
    if not shutil.which("dpkg-deb"):
        raise SystemExit("dpkg-deb fehlt; unter Debian/Ubuntu das Paket dpkg installieren.")
    artifacts: list[Path] = []
    for edition in EDITIONS:
        with tempfile.TemporaryDirectory(prefix=f"{edition.package}-deb-", dir=ROOT / "build") as temp:
            stage = Path(temp) / "root"
            write_debian_control(stage, edition, version, deb_arch)
            populate_payload(stage, edition)
            normalize_permissions(stage, edition.executable)
            artifact = OUTPUT / f"{edition.package}_{version}_{deb_arch}.deb"
            subprocess.run(
                ["dpkg-deb", "--build", "--root-owner-group", str(stage), str(artifact)],
                check=True,
            )
            artifacts.append(artifact)
    return artifacts


def rpm_spec(edition: Edition, version: str, rpm_arch: str) -> str:
    return f"""%global debug_package %{{nil}}
Name:           {edition.package}
Version:        {version}
Release:        1%{{?dist}}
Summary:        {edition.summary}
License:        GPL-3.0-or-later
URL:            {HOMEPAGE}
Source0:        {edition.executable}
Source1:        README.md
Source2:        LICENSE
BuildArch:      {rpm_arch}
Requires:       glibc >= 2.34
Requires:       zlib

%description
{edition.description}

%prep

%build

%install
install -Dpm 0755 %{{SOURCE0}} %{{buildroot}}%{{_bindir}}/{edition.executable}
install -Dpm 0644 %{{SOURCE1}} %{{buildroot}}%{{_docdir}}/{edition.package}/README.md
install -Dpm 0644 %{{SOURCE2}} %{{buildroot}}%{{_licensedir}}/{edition.package}/LICENSE

%files
%{{_bindir}}/{edition.executable}
%doc %{{_docdir}}/{edition.package}/README.md
%license %{{_licensedir}}/{edition.package}/LICENSE

%changelog
* Sun Jul 05 2026 synadm-tui contributors - {version}-1
- Automated local package build
"""


def build_rpm(version: str, rpm_arch: str) -> list[Path]:
    rpmbuild_command = shutil.which("rpmbuild")
    if not rpmbuild_command:
        raise SystemExit("rpmbuild fehlt; unter Debian/Ubuntu das Paket rpm installieren.")
    artifacts: list[Path] = []
    topdir = ROOT / "build" / "rpm"
    if topdir.exists():
        shutil.rmtree(topdir)
    for directory in ("BUILD", "BUILDROOT", "RPMS", "SOURCES", "SPECS", "SRPMS"):
        (topdir / directory).mkdir(parents=True, exist_ok=True)
    (topdir / "rpmdb").mkdir()
    (topdir / "tmp").mkdir()
    shutil.copy2(ROOT / "README.md", topdir / "SOURCES" / "README.md")
    shutil.copy2(ROOT / "LICENSE", topdir / "SOURCES" / "LICENSE")
    for edition in EDITIONS:
        shutil.copy2(DIST / edition.executable, topdir / "SOURCES" / edition.executable)
        spec = topdir / "SPECS" / f"{edition.package}.spec"
        spec.write_text(rpm_spec(edition, version, rpm_arch), encoding="utf-8")
        command = [
            rpmbuild_command,
            "-bb",
            "--define",
            f"_topdir {topdir}",
            "--define",
            f"_dbpath {topdir / 'rpmdb'}",
            "--define",
            f"_tmppath {topdir / 'tmp'}",
        ]
        # Supports an unpacked, user-local Debian rpm package as well as a
        # conventional system-wide rpmbuild installation.
        local_config = Path(rpmbuild_command).resolve().parent.parent / "lib" / "rpm"
        if local_config != Path("/usr/lib/rpm") and (local_config / "brp-compress").is_file():
            command.extend(("--define", f"_rpmconfigdir {local_config}"))
        command.append(str(spec))
        subprocess.run(command, check=True)
    for built in sorted((topdir / "RPMS").rglob("*.rpm")):
        target = OUTPUT / built.name
        shutil.copy2(built, target)
        artifacts.append(target)
    sign_rpms(artifacts)
    return artifacts


def rpm_signing_settings() -> tuple[str, Path] | None:
    key_file = ROOT / "packaging" / "RPM-SIGNING-KEY-ID"
    key_id = os.environ.get("SYNADM_RPM_SIGNING_KEY", "").strip()
    if not key_id:
        try:
            key_id = key_file.read_text(encoding="utf-8").strip()
        except OSError:
            return None
    signing_home = Path(
        os.environ.get("SYNADM_RPM_GNUPGHOME", str(DEFAULT_RPM_SIGNING_HOME))
    ).expanduser()
    private_keys = signing_home / "private-keys-v1.d"
    if not private_keys.is_dir() or not any(private_keys.iterdir()):
        print("Hinweis: Kein privater RPM-Schlüssel vorhanden; RPM bleibt unsigniert.", file=sys.stderr)
        return None
    return key_id, signing_home


def sign_rpms(artifacts: list[Path]) -> None:
    settings = rpm_signing_settings()
    if settings is None:
        return
    rpmsign = shutil.which("rpmsign")
    if not rpmsign:
        raise SystemExit("rpmsign fehlt; unter Debian/Ubuntu das Paket rpm installieren.")
    key_id, signing_home = settings
    environment = os.environ.copy()
    environment["GNUPGHOME"] = str(signing_home)
    for artifact in artifacts:
        subprocess.run(
            [
                rpmsign,
                "--addsign",
                "--define",
                f"_gpg_name {key_id}",
                "--define",
                f"_gpg_path {signing_home}",
                "--define",
                "__gpg /usr/bin/gpg",
                str(artifact),
            ],
            check=True,
            env=environment,
        )


def checksum_file(artifacts: list[Path]) -> Path:
    import hashlib

    target = OUTPUT / "SHA256SUMS"
    lines = [f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}" for path in artifacts]
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--format",
        choices=("all", "deb", "rpm"),
        default="all",
        help="zu bauendes Paketformat (Standard: all)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    require_native_files()
    version = project_version()
    deb_arch, rpm_arch = architecture()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (ROOT / "build").mkdir(parents=True, exist_ok=True)
    artifacts: list[Path] = []
    if args.format in ("all", "deb"):
        artifacts.extend(build_deb(version, deb_arch))
    if args.format in ("all", "rpm"):
        artifacts.extend(build_rpm(version, rpm_arch))
    checksum = checksum_file(artifacts)
    for artifact in (*artifacts, checksum):
        print(artifact.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
