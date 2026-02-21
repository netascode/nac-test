# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for PyATSOrchestrator dry-run functionality."""

from pathlib import Path
from unittest.mock import patch

import pytest
from _pytest.monkeypatch import MonkeyPatch

from nac_test.pyats_core.orchestrator import PyATSOrchestrator


class TestOrchestratorDryRun:
    """Tests for PyATSOrchestrator dry_run parameter and behavior."""

    def test_orchestrator_accepts_dry_run_parameter(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that PyATSOrchestrator accepts dry_run parameter."""
        # Set up controller env
        monkeypatch.setenv("ACI_URL", "https://apic.test.com")
        monkeypatch.setenv("ACI_USERNAME", "admin")
        monkeypatch.setenv("ACI_PASSWORD", "password")

        # Create test directories
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        merged_file = output_dir / "merged.yaml"
        merged_file.write_text("test: data")

        # Initialize with dry_run=True
        orchestrator = PyATSOrchestrator(
            data_paths=[tmp_path / "data"],
            test_dir=test_dir,
            output_dir=output_dir,
            merged_data_filename="merged.yaml",
            dry_run=True,
        )

        assert orchestrator.dry_run is True

    def test_orchestrator_dry_run_defaults_to_false(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that dry_run defaults to False when not specified."""
        # Set up controller env
        monkeypatch.setenv("ACI_URL", "https://apic.test.com")
        monkeypatch.setenv("ACI_USERNAME", "admin")
        monkeypatch.setenv("ACI_PASSWORD", "password")

        # Create test directories
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        merged_file = output_dir / "merged.yaml"
        merged_file.write_text("test: data")

        # Initialize without dry_run parameter
        orchestrator = PyATSOrchestrator(
            data_paths=[tmp_path / "data"],
            test_dir=test_dir,
            output_dir=output_dir,
            merged_data_filename="merged.yaml",
        )

        assert orchestrator.dry_run is False

    def test_dry_run_prints_summary_and_skips_execution(
        self,
        tmp_path: Path,
        monkeypatch: MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that dry_run mode prints test summary and skips execution."""
        # Set up controller env
        monkeypatch.setenv("ACI_URL", "https://apic.test.com")
        monkeypatch.setenv("ACI_USERNAME", "admin")
        monkeypatch.setenv("ACI_PASSWORD", "password")

        # Create test directories
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        merged_file = output_dir / "merged.yaml"
        merged_file.write_text("test: data")

        # Create mock test files
        api_test = test_dir / "test_api.py"
        api_test.write_text("# API test")

        orchestrator = PyATSOrchestrator(
            data_paths=[tmp_path / "data"],
            test_dir=test_dir,
            output_dir=output_dir,
            merged_data_filename="merged.yaml",
            dry_run=True,
        )

        # Mock the discovery to return test files
        mock_api_tests = [api_test]
        mock_d2d_tests: list[Path] = []

        with patch.object(
            orchestrator.test_discovery, "discover_pyats_tests"
        ) as mock_discover:
            mock_discover.return_value = (mock_api_tests, [])

            with patch.object(
                orchestrator.test_discovery, "categorize_tests_by_type"
            ) as mock_categorize:
                mock_categorize.return_value = (mock_api_tests, mock_d2d_tests)

                with patch.object(orchestrator, "validate_environment"):
                    # Run tests - should NOT execute actual tests
                    result = orchestrator.run_tests()

        # Verify dry-run output
        captured = capsys.readouterr()
        assert "DRY-RUN MODE" in captured.out
        assert "test_api.py" in captured.out
        assert "dry-run complete" in captured.out

        # Verify results indicate not_run
        assert result.api is not None
        assert result.api.reason == "dry-run mode"
        assert result.d2d is None  # No D2D tests

    def test_dry_run_returns_not_run_results_for_api_and_d2d(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that dry_run returns not_run results for both API and D2D tests."""
        # Set up controller env
        monkeypatch.setenv("ACI_URL", "https://apic.test.com")
        monkeypatch.setenv("ACI_USERNAME", "admin")
        monkeypatch.setenv("ACI_PASSWORD", "password")

        # Create test directories
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        d2d_dir = test_dir / "d2d"
        d2d_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        merged_file = output_dir / "merged.yaml"
        merged_file.write_text("test: data")

        # Create mock test files
        api_test = test_dir / "test_api.py"
        api_test.write_text("# API test")
        d2d_test = d2d_dir / "test_d2d.py"
        d2d_test.write_text("# D2D test")

        orchestrator = PyATSOrchestrator(
            data_paths=[tmp_path / "data"],
            test_dir=test_dir,
            output_dir=output_dir,
            merged_data_filename="merged.yaml",
            dry_run=True,
        )

        with patch.object(
            orchestrator.test_discovery, "discover_pyats_tests"
        ) as mock_discover:
            mock_discover.return_value = ([api_test, d2d_test], [])

            with patch.object(
                orchestrator.test_discovery, "categorize_tests_by_type"
            ) as mock_categorize:
                mock_categorize.return_value = ([api_test], [d2d_test])

                with patch.object(orchestrator, "validate_environment"):
                    result = orchestrator.run_tests()

        # Both API and D2D should have not_run results
        assert result.api is not None
        assert result.api.reason == "dry-run mode"
        assert result.d2d is not None
        assert result.d2d.reason == "dry-run mode"

    def test_dry_run_does_not_execute_tests(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that dry_run mode does not execute tests."""
        monkeypatch.setenv("ACI_URL", "https://apic.test.com")
        monkeypatch.setenv("ACI_USERNAME", "admin")
        monkeypatch.setenv("ACI_PASSWORD", "password")

        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        merged_file = output_dir / "merged.yaml"
        merged_file.write_text("test: data")

        api_test = test_dir / "test_api.py"
        api_test.write_text("# API test")

        orchestrator = PyATSOrchestrator(
            data_paths=[tmp_path / "data"],
            test_dir=test_dir,
            output_dir=output_dir,
            merged_data_filename="merged.yaml",
            dry_run=True,
        )

        with patch.object(
            orchestrator.test_discovery, "discover_pyats_tests"
        ) as mock_discover:
            mock_discover.return_value = ([api_test], [])

            with patch.object(
                orchestrator.test_discovery, "categorize_tests_by_type"
            ) as mock_categorize:
                mock_categorize.return_value = ([api_test], [])

                with patch.object(orchestrator, "validate_environment"):
                    with patch.object(
                        orchestrator, "_execute_api_tests_standard"
                    ) as mock_execute:
                        orchestrator.run_tests()

        mock_execute.assert_not_called()

    def test_dry_run_empty_test_lists(
        self,
        tmp_path: Path,
        monkeypatch: MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test dry_run with no tests discovered returns empty PyATSResults."""
        # Set up controller env
        monkeypatch.setenv("ACI_URL", "https://apic.test.com")
        monkeypatch.setenv("ACI_USERNAME", "admin")
        monkeypatch.setenv("ACI_PASSWORD", "password")

        # Create test directories
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        merged_file = output_dir / "merged.yaml"
        merged_file.write_text("test: data")

        orchestrator = PyATSOrchestrator(
            data_paths=[tmp_path / "data"],
            test_dir=test_dir,
            output_dir=output_dir,
            merged_data_filename="merged.yaml",
            dry_run=True,
        )

        with patch.object(
            orchestrator.test_discovery, "discover_pyats_tests"
        ) as mock_discover:
            # No tests discovered
            mock_discover.return_value = ([], [])

            with patch.object(orchestrator, "validate_environment"):
                result = orchestrator.run_tests()

        # Should return empty results (no tests found message)
        captured = capsys.readouterr()
        assert "No PyATS test files" in captured.out
        assert result.api is None
        assert result.d2d is None
