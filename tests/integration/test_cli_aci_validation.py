# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Integration tests for ACI defaults validation in the CLI.

These tests verify the end-to-end CLI behavior for ACI defaults validation,
ensuring the wiring between main.py, validators, and UI components works
correctly as a complete system.
"""

import os
import shutil
import subprocess
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from nac_test.cli.main import app

runner = CliRunner()


class TestCliAciValidationIntegration:
    """Integration tests for ACI defaults validation through the CLI."""

    @pytest.fixture(autouse=True)
    def clean_controller_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Clear all controller-related environment variables before each test.

        Ensures tests run in isolation regardless of the caller's shell environment.
        """
        for key in list(os.environ.keys()):
            if any(
                prefix in key
                for prefix in ["ACI_", "SDWAN_", "CC_", "MERAKI_", "FMC_", "ISE_"]
            ):
                monkeypatch.delenv(key, raising=False)

    @pytest.fixture
    def minimal_test_env(
        self, tmp_path: Path
    ) -> Generator[dict[str, Path], None, None]:
        """Create a minimal test environment with required directories and files."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        output_dir = tmp_path / "output"

        # Create minimal YAML file (without defaults)
        yaml_file = data_dir / "config.yaml"
        yaml_file.write_text("some_config:\n  key: value\n")

        yield {
            "data_dir": data_dir,
            "templates_dir": templates_dir,
            "output_dir": output_dir,
            "yaml_file": yaml_file,
        }

    def test_cli_validation_triggers_when_aci_url_set_and_no_defaults(
        self,
        minimal_test_env: dict[str, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """CLI should fail with defaults banner when ACI_URL is set but no defaults provided."""
        monkeypatch.setenv("ACI_URL", "https://apic.example.com")

        result = runner.invoke(
            app,
            [
                "-d",
                str(minimal_test_env["data_dir"]),
                "-t",
                str(minimal_test_env["templates_dir"]),
                "-o",
                str(minimal_test_env["output_dir"]),
            ],
        )

        # Should fail with exit code 1 and show the defaults banner
        assert result.exit_code == 1
        assert "DEFAULTS FILE REQUIRED FOR ACI" in result.stdout

    def test_cli_validation_passes_when_aci_url_not_set(
        self,
        minimal_test_env: dict[str, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """CLI should skip ACI validation when ACI_URL is not set."""
        # Ensure ACI_URL is not set
        monkeypatch.delenv("ACI_URL", raising=False)

        # We need to mock the DataMerger and orchestrator since we don't have full environment
        with (
            patch("nac_test.cli.main.DataMerger") as mock_merger,
            patch("nac_test.cli.main.CombinedOrchestrator") as mock_orchestrator,
        ):
            mock_merger.merge_data_files.return_value = {"test": "data"}
            mock_orchestrator_instance = MagicMock()
            mock_orchestrator.return_value = mock_orchestrator_instance

            result = runner.invoke(
                app,
                [
                    "-d",
                    str(minimal_test_env["data_dir"]),
                    "-t",
                    str(minimal_test_env["templates_dir"]),
                    "-o",
                    str(minimal_test_env["output_dir"]),
                ],
            )

            # Should NOT fail due to missing defaults (might fail for other reasons)
            assert "DEFAULTS FILE REQUIRED FOR ACI" not in result.stdout

    def test_cli_validation_passes_when_defaults_path_provided(
        self,
        minimal_test_env: dict[str, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """CLI should pass validation when defaults path is provided."""
        monkeypatch.setenv("ACI_URL", "https://apic.example.com")

        # Create a defaults directory
        defaults_dir = minimal_test_env["data_dir"].parent / "defaults"
        defaults_dir.mkdir()
        defaults_file = defaults_dir / "defaults.yaml"
        defaults_file.write_text("defaults:\n  apic:\n    version: 5.2\n")

        # Mock the expensive operations since we just want to test validation passes
        with (
            patch("nac_test.cli.main.DataMerger") as mock_merger,
            patch("nac_test.cli.main.CombinedOrchestrator") as mock_orchestrator,
        ):
            mock_merger.merge_data_files.return_value = {"test": "data"}
            mock_orchestrator_instance = MagicMock()
            mock_orchestrator.return_value = mock_orchestrator_instance

            result = runner.invoke(
                app,
                [
                    "-d",
                    str(minimal_test_env["data_dir"]),
                    "-d",
                    str(defaults_dir),
                    "-t",
                    str(minimal_test_env["templates_dir"]),
                    "-o",
                    str(minimal_test_env["output_dir"]),
                ],
            )

            # Should NOT show defaults banner - validation passed
            assert "DEFAULTS FILE REQUIRED FOR ACI" not in result.stdout

    def test_cli_validation_passes_when_defaults_structure_in_yaml(
        self,
        minimal_test_env: dict[str, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """CLI should pass validation when YAML contains defaults.apic structure."""
        monkeypatch.setenv("ACI_URL", "https://apic.example.com")

        # Add defaults structure to existing YAML file
        yaml_file = minimal_test_env["data_dir"] / "config.yaml"
        yaml_file.write_text(
            "defaults:\n  apic:\n    version: 5.2\nother_config:\n  key: value\n"
        )

        # Mock the expensive operations
        with (
            patch("nac_test.cli.main.DataMerger") as mock_merger,
            patch("nac_test.cli.main.CombinedOrchestrator") as mock_orchestrator,
        ):
            mock_merger.merge_data_files.return_value = {"test": "data"}
            mock_orchestrator_instance = MagicMock()
            mock_orchestrator.return_value = mock_orchestrator_instance

            result = runner.invoke(
                app,
                [
                    "-d",
                    str(minimal_test_env["data_dir"]),
                    "-t",
                    str(minimal_test_env["templates_dir"]),
                    "-o",
                    str(minimal_test_env["output_dir"]),
                ],
            )

            # Should NOT show defaults banner - validation passed via content check
            assert "DEFAULTS FILE REQUIRED FOR ACI" not in result.stdout


class TestCliAciValidationSubprocess:
    """Subprocess-based integration tests for CLI behavior.

    These tests run the actual CLI as a subprocess to verify the complete
    end-to-end behavior including entry point wiring.
    """

    @pytest.fixture(autouse=True)
    def clean_controller_env(self) -> Generator[None, None, None]:
        """Clear ACI environment variables for subprocess tests."""
        original_env = os.environ.copy()
        # Clear controller vars
        for key in list(os.environ.keys()):
            if any(
                prefix in key
                for prefix in ["ACI_", "SDWAN_", "CC_", "MERAKI_", "FMC_", "ISE_"]
            ):
                del os.environ[key]
        yield
        # Restore original environment
        os.environ.clear()
        os.environ.update(original_env)

    @pytest.fixture
    def cli_test_env(self, tmp_path: Path) -> Generator[dict[str, Path], None, None]:
        """Create a minimal test environment for subprocess tests."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        output_dir = tmp_path / "output"

        # Create minimal YAML file without defaults
        yaml_file = data_dir / "config.yaml"
        yaml_file.write_text("some_config:\n  key: value\n")

        yield {
            "data_dir": data_dir,
            "templates_dir": templates_dir,
            "output_dir": output_dir,
        }

    @pytest.mark.skipif(
        shutil.which("nac-test") is None,
        reason="nac-test CLI not installed in PATH",
    )
    def test_subprocess_validation_fails_with_aci_url_no_defaults(
        self, cli_test_env: dict[str, Path]
    ) -> None:
        """Subprocess test: CLI fails when ACI_URL set without defaults."""
        env = os.environ.copy()
        env["ACI_URL"] = "https://apic.example.com"

        result = subprocess.run(
            [
                "nac-test",
                "-d",
                str(cli_test_env["data_dir"]),
                "-t",
                str(cli_test_env["templates_dir"]),
                "-o",
                str(cli_test_env["output_dir"]),
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 1
        assert "DEFAULTS FILE REQUIRED FOR ACI" in result.stdout

    @pytest.mark.skipif(
        shutil.which("nac-test") is None,
        reason="nac-test CLI not installed in PATH",
    )
    def test_subprocess_validation_skips_without_aci_url(
        self, cli_test_env: dict[str, Path]
    ) -> None:
        """Subprocess test: CLI skips ACI validation when ACI_URL not set."""
        env = os.environ.copy()
        # Explicitly remove ACI_URL if present
        env.pop("ACI_URL", None)

        result = subprocess.run(
            [
                "nac-test",
                "-d",
                str(cli_test_env["data_dir"]),
                "-t",
                str(cli_test_env["templates_dir"]),
                "-o",
                str(cli_test_env["output_dir"]),
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Should NOT show the defaults banner (may fail for other reasons)
        assert "DEFAULTS FILE REQUIRED FOR ACI" not in result.stdout
