# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Shared fixtures for PyATS orchestrator tests."""

from pathlib import Path
from typing import NamedTuple

import pytest


class PyATSTestDirs(NamedTuple):
    """Directory structure for PyATS orchestrator tests."""

    test_dir: Path
    output_dir: Path
    merged_file: Path


@pytest.fixture()
def aci_controller_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set ACI controller environment variables."""
    monkeypatch.setenv("ACI_URL", "https://apic.example.invalid")
    monkeypatch.setenv("ACI_USERNAME", "admin")
    monkeypatch.setenv("ACI_PASSWORD", "password")


@pytest.fixture()
def pyats_test_dirs(tmp_path: Path) -> PyATSTestDirs:
    """Create standard directory structure for PyATS orchestrator tests."""
    test_dir = tmp_path / "tests"
    test_dir.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    merged_file = output_dir / "merged.yaml"
    merged_file.write_text("test: data")
    return PyATSTestDirs(
        test_dir=test_dir, output_dir=output_dir, merged_file=merged_file
    )
