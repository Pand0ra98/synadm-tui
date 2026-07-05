from __future__ import annotations

import importlib.util
import sys
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
        self.assertEqual(build_packages.project_version(), "0.15")

    def test_supported_architecture_mapping(self) -> None:
        with mock.patch.object(build_packages.platform, "machine", return_value="x86_64"):
            self.assertEqual(build_packages.architecture(), ("amd64", "x86_64"))

    def test_rpm_spec_contains_expected_binary(self) -> None:
        edition = build_packages.EDITIONS[0]
        spec = build_packages.rpm_spec(edition, "0.15", "x86_64")
        self.assertIn("Name:           synadm-tui", spec)
        self.assertIn("%{_bindir}/synadm-tui", spec)
        self.assertIn("Requires:       glibc >= 2.34", spec)
        self.assertIn("Requires:       zlib", spec)


if __name__ == "__main__":
    unittest.main()
