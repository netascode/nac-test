# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Tests for CombinedOrchestrator macOS unsupported Python defense-in-depth exit."""

from pathlib import Path
from unittest.mock import patch

import pytest
import typer
from _pytest.monkeypatch import MonkeyPatch

from nac_test.combined_orchestrator import CombinedOrchestrator


class TestOrchestratorUnsupportedPythonExit:
    """Tests for the orchestrator-level macOS unsupported Python hard exit."""

    @pytest.fixture(autouse=True)
    def _clean_env(self, clean_controller_env: None) -> None:
        """Apply shared clean_controller_env fixture to all tests in this class."""

    def _make_orchestrator(
        self, tmp_path: Path, monkeypatch: MonkeyPatch, *, dev_pyats_only: bool = True
    ) -> CombinedOrchestrator:
        """Create a CombinedOrchestrator with ACI credentials for testing."""
        monkeypatch.setenv("ACI_URL", "https://apic.test.com")
        monkeypatch.setenv("ACI_USERNAME", "admin")
        monkeypatch.setenv("ACI_PASSWORD", "password")

        data_dir = tmp_path / "data"
        data_dir.mkdir(exist_ok=True)
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir(exist_ok=True)
        output_dir = tmp_path / "output"

        return CombinedOrchestrator(
            data_paths=[data_dir],
            templates_dir=templates_dir,
            output_dir=output_dir,
            merged_data_filename="merged.yaml",
            dev_pyats_only=dev_pyats_only,
        )

    def test_check_python_version_exits_on_unsupported(self) -> None:
        """_check_python_version must raise typer.Exit(1) on unsupported macOS Python."""
        with (
            patch("nac_test.utils.platform.IS_UNSUPPORTED_MACOS_PYTHON", True),
            patch("nac_test.utils.platform.typer.secho"),
            patch("nac_test.utils.platform.typer.echo"),
        ):
            with pytest.raises(typer.Exit) as exc_info:
                CombinedOrchestrator._check_python_version()

            assert exc_info.value.exit_code == 1

    def test_check_python_version_passes_on_supported_platform(self) -> None:
        """_check_python_version must NOT exit on supported platforms."""
        with patch("nac_test.utils.platform.IS_UNSUPPORTED_MACOS_PYTHON", False):
            CombinedOrchestrator._check_python_version()

    def test_pyats_only_mode_triggers_check(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Dev pyats-only mode must call _check_python_version and exit on unsupported macOS Python."""
        orchestrator = self._make_orchestrator(
            tmp_path, monkeypatch, dev_pyats_only=True
        )

        with (
            patch("nac_test.utils.platform.IS_UNSUPPORTED_MACOS_PYTHON", True),
            patch("nac_test.utils.platform.typer.secho"),
            patch("nac_test.utils.platform.typer.echo"),
        ):
            with pytest.raises(typer.Exit) as exc_info:
                orchestrator.run_tests()

            assert exc_info.value.exit_code == 1
