# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Shared fixtures for PyATS orchestrator tests.

NOTE: This module intentionally duplicates some patterns from tests/unit/conftest.py.
Issue #541 will merge tests/pyats_core/ into tests/unit/, at which point these
fixtures should be consolidated into a single conftest.py.
"""

import os
from pathlib import Path
from typing import NamedTuple

import pytest
from _pytest.monkeypatch import MonkeyPatch

CONTROLLER_ENV_PREFIXES = ("ACI_", "SDWAN_", "CC_", "MERAKI_", "FMC_", "ISE_")


class PyATSTestDirs(NamedTuple):
    """Directory structure for PyATS orchestrator tests."""

    test_dir: Path
    output_dir: Path
    merged_file: Path


@pytest.fixture()
def clean_controller_env(monkeypatch: MonkeyPatch) -> None:
    """Clear all controller-related environment variables.

    Ensures tests run in isolation regardless of the caller's shell environment.
    """
    for key in list(os.environ.keys()):
        if any(prefix in key for prefix in CONTROLLER_ENV_PREFIXES):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture()
def aci_controller_env(monkeypatch: MonkeyPatch) -> None:
    """Set ACI controller environment variables."""
    monkeypatch.setenv("ACI_URL", "https://apic.test.com")
    monkeypatch.setenv("ACI_USERNAME", "admin")
    monkeypatch.setenv("ACI_PASSWORD", "password")


@pytest.fixture()
def sdwan_controller_env(monkeypatch: MonkeyPatch) -> None:
    """Set SD-WAN controller environment variables."""
    monkeypatch.setenv("SDWAN_URL", "https://vmanage.test.com")
    monkeypatch.setenv("SDWAN_USERNAME", "admin")
    monkeypatch.setenv("SDWAN_PASSWORD", "password")


@pytest.fixture()
def cc_controller_env(monkeypatch: MonkeyPatch) -> None:
    """Set Catalyst Center controller environment variables."""
    monkeypatch.setenv("CC_URL", "https://cc.test.com")
    monkeypatch.setenv("CC_USERNAME", "admin")
    monkeypatch.setenv("CC_PASSWORD", "password")


@pytest.fixture()
def pyats_test_dirs(tmp_path: Path) -> PyATSTestDirs:
    """Create standard directory structure for PyATS orchestrator tests.

    Returns:
        PyATSTestDirs with test_dir, output_dir, and merged_file paths.
    """
    test_dir = tmp_path / "tests"
    test_dir.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    merged_file = output_dir / "merged.yaml"
    merged_file.write_text("test: data")
    return PyATSTestDirs(
        test_dir=test_dir, output_dir=output_dir, merged_file=merged_file
    )
