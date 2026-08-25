from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("build_packages", ROOT / "scripts" / "build_packages.py")
assert SPEC and SPEC.loader
build_packages = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = build_packages
SPEC.loader.exec_module(build_packages)


class PackageBuildTests(unittest.TestCase):
    def test_project_version_matches_current_release(self) -> None:
        self.assertEqual(build_packages.project_version(), "0.20")

    def test_supported_architecture_mapping(self) -> None:
        with mock.patch.object(build_packages.platform, "machine", return_value="x86_64"):
            self.assertEqual(build_packages.architecture(), ("amd64", "x86_64"))

    def test_debian_package_name_does_not_contain_version(self) -> None:
        edition = build_packages.EDITIONS[0]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / edition.executable).write_bytes(b"test executable")
            stage = root / "stage"
            with mock.patch.object(build_packages, "DIST", root):
                build_packages.write_debian_control(stage, edition, "0.20", "amd64")
            control = (stage / "DEBIAN" / "control").read_text(encoding="utf-8")

        self.assertIn("Package: synadm-tui\n", control)
        self.assertIn("Version: 0.20\n", control)
        self.assertNotIn("Package: synadm-tui=0.20", control)
        self.assertIn("ca-certificates", control)
        self.assertIn("openssl", control)
        self.assertIn("python3", control)
        self.assertIn("python3-venv", control)
        self.assertIn("python3-pip", control)
        self.assertIn("pipx", control)

    def test_rpm_spec_contains_expected_binary(self) -> None:
        edition = build_packages.EDITIONS[0]
        spec = build_packages.rpm_spec(edition, "0.20", "x86_64")
        self.assertIn("Name:           synadm-tui", spec)
        self.assertIn("%{_bindir}/synadm-tui", spec)
        self.assertIn("Requires:       glibc >= 2.34", spec)
        self.assertIn("Requires:       zlib", spec)
        self.assertIn("Requires:       ca-certificates", spec)
        self.assertIn("Requires:       openssl-libs", spec)
        self.assertIn("Requires:       python3", spec)
        self.assertIn("Requires:       python3-pip", spec)
        self.assertIn("Requires:       pipx", spec)

    def test_builds_standard_and_thueringen_editions(self) -> None:
        packages = {edition.package for edition in build_packages.EDITIONS}
        executables = {edition.executable for edition in build_packages.EDITIONS}
        self.assertEqual(packages, {"synadm-tui", "synadm-tui-thueringen"})
        self.assertEqual(executables, {"synadm-tui", "synadm-tui-thueringen"})

    def test_official_rpm_signing_key_is_declared(self) -> None:
        key = (ROOT / "packaging" / "RPM-SIGNING-KEY-ID").read_text(encoding="utf-8").strip()
        self.assertEqual(key, "A58923624002F769A7683FD6C18758AECA92C968")


if __name__ == "__main__":
    unittest.main()
