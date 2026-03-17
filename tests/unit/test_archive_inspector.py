# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for ArchiveInspector.extract_test_results() method."""

import json
import zipfile
from pathlib import Path

import pytest

from nac_test.core.constants import PYATS_RESULTS_DIRNAME
from nac_test.pyats_core.reporting.utils.archive_inspector import ArchiveInspector


class TestExtractTestResults:
    """Tests for ArchiveInspector.extract_test_results() method."""

    def test_extract_test_results_valid_archive(self, tmp_path: Path) -> None:
        """Test extraction of test results from a valid archive with results.json."""
        # Create a mock results.json structure with testscript paths
        # This matches real PyATS output where testscript contains the full path
        results_data = {
            "report": {
                "tasks": [
                    {
                        "name": "verify_tenant",
                        "testscript": "/path/to/templates/api/tenants/verify_tenant.py",
                        "result": {"value": "passed"},
                        "runtime": 1.234,
                        "sections": [
                            {"description": "Verify Tenant Configuration\nExtra line"}
                        ],
                    },
                    {
                        "name": "verify_fabric",
                        "testscript": "/path/to/templates/api/fabrics/verify_fabric.py",
                        "result": {"value": "failed"},
                        "runtime": 2.567,
                        "sections": [{"description": "Verify Fabric Settings"}],
                    },
                ]
            }
        }

        # Create archive with results.json
        archive_path = tmp_path / "test_archive.zip"
        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr("results.json", json.dumps(results_data))

        # Extract results
        test_dir = Path("/path/to/templates")
        results = ArchiveInspector.extract_test_results(archive_path, test_dir)

        # Verify results - keys should be derived from testscript path
        assert len(results) == 2

        # Key should be derived from testscript: "api.tenants.verify_tenant"
        assert "api.tenants.verify_tenant" in results
        tenant_result = results["api.tenants.verify_tenant"]
        assert tenant_result["status"] == "passed"
        assert tenant_result["duration"] == 1.234
        assert tenant_result["title"] == "Verify Tenant Configuration"
        assert tenant_result["test_id"] == 0

        # Key should be derived from testscript: "api.fabrics.verify_fabric"
        assert "api.fabrics.verify_fabric" in results
        fabric_result = results["api.fabrics.verify_fabric"]
        assert fabric_result["status"] == "failed"
        assert fabric_result["duration"] == 2.567
        assert fabric_result["title"] == "Verify Fabric Settings"

    def test_extract_test_results_bad_zip_file(self, tmp_path: Path) -> None:
        """Test that BadZipFile is raised for corrupted archives."""
        # Create a corrupted zip file
        archive_path = tmp_path / "corrupted.zip"
        archive_path.write_text("not a valid zip file")

        with pytest.raises(zipfile.BadZipFile):
            ArchiveInspector.extract_test_results(archive_path, tmp_path)

    def test_extract_test_results_missing_results_json(self, tmp_path: Path) -> None:
        """Test that empty dict is returned when results.json is missing."""
        # Create archive without results.json
        archive_path = tmp_path / "no_results.zip"
        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr("some_other_file.txt", "content")

        results = ArchiveInspector.extract_test_results(archive_path, tmp_path)

        assert results == {}

    def test_extract_test_results_file_not_found(self, tmp_path: Path) -> None:
        """Test that FileNotFoundError is raised for non-existent archives."""
        archive_path = tmp_path / "nonexistent.zip"

        with pytest.raises(FileNotFoundError):
            ArchiveInspector.extract_test_results(archive_path, tmp_path)

    @pytest.mark.parametrize(
        "pyats_status,expected_status",
        [
            ("passed", "passed"),
            ("PASSED", "passed"),
            ("failed", "failed"),
            ("FAILED", "failed"),
            ("errored", "errored"),
            ("ERRORED", "errored"),
            ("skipped", "skipped"),
            ("SKIPPED", "skipped"),
            ("blocked", "blocked"),
            ("BLOCKED", "blocked"),
        ],
    )
    def test_extract_test_results_status_mapping(
        self, tmp_path: Path, pyats_status: str, expected_status: str
    ) -> None:
        """Test that all PyATS result values are correctly mapped."""
        results_data = {
            "report": {
                "tasks": [
                    {
                        "name": "test.case",
                        "result": {"value": pyats_status},
                        "runtime": 1.0,
                        "sections": [],
                    }
                ]
            }
        }

        archive_path = tmp_path / "status_test.zip"
        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr("results.json", json.dumps(results_data))

        results = ArchiveInspector.extract_test_results(archive_path, tmp_path)

        assert results["test.case"]["status"] == expected_status

    def test_extract_test_results_unknown_status_preserved(
        self, tmp_path: Path
    ) -> None:
        """Test that unknown status values are preserved as-is."""
        results_data = {
            "report": {
                "tasks": [
                    {
                        "name": "test.case",
                        "result": {"value": "custom_status"},
                        "runtime": 1.0,
                        "sections": [],
                    }
                ]
            }
        }

        archive_path = tmp_path / "custom_status.zip"
        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr("results.json", json.dumps(results_data))

        results = ArchiveInspector.extract_test_results(archive_path, tmp_path)

        assert results["test.case"]["status"] == "custom_status"

    def test_extract_test_results_nested_results_json(self, tmp_path: Path) -> None:
        """Test extraction when results.json is in a nested directory."""
        results_data = {
            "report": {
                "tasks": [
                    {
                        "name": "nested.test",
                        "result": {"value": "passed"},
                        "runtime": 0.5,
                        "sections": [{"description": "Nested Test"}],
                    }
                ]
            }
        }

        archive_path = tmp_path / "nested.zip"
        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr("subdir/results.json", json.dumps(results_data))

        results = ArchiveInspector.extract_test_results(archive_path, tmp_path)

        assert "nested.test" in results
        assert results["nested.test"]["status"] == "passed"

    def test_extract_test_results_empty_task_name_skipped(self, tmp_path: Path) -> None:
        """Test that tasks with empty names are skipped."""
        results_data = {
            "report": {
                "tasks": [
                    {
                        "name": "",
                        "result": {"value": "passed"},
                        "runtime": 1.0,
                        "sections": [],
                    },
                    {
                        "name": "valid.test",
                        "result": {"value": "passed"},
                        "runtime": 1.0,
                        "sections": [],
                    },
                ]
            }
        }

        archive_path = tmp_path / "empty_name.zip"
        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr("results.json", json.dumps(results_data))

        results = ArchiveInspector.extract_test_results(archive_path, tmp_path)

        assert len(results) == 1
        assert "valid.test" in results
        assert "" not in results

    def test_extract_test_results_title_fallback_to_task_name(
        self, tmp_path: Path
    ) -> None:
        """Test that task name is used as title when sections are empty."""
        results_data = {
            "report": {
                "tasks": [
                    {
                        "name": "test.without.description",
                        "result": {"value": "passed"},
                        "runtime": 1.0,
                        "sections": [],
                    }
                ]
            }
        }

        archive_path = tmp_path / "no_description.zip"
        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr("results.json", json.dumps(results_data))

        results = ArchiveInspector.extract_test_results(archive_path, tmp_path)

        assert (
            results["test.without.description"]["title"] == "test.without.description"
        )


class TestDeriveTestNameFromPath:
    """Tests for ArchiveInspector._derive_test_name_from_path() helper."""

    def test_derives_name_from_testscript_path(self) -> None:
        """Test that test name is correctly derived from testscript path."""
        testscript = "/path/to/templates/nrfu/verify_device_status.py"
        test_dir = Path("/path/to/templates")
        result = ArchiveInspector._derive_test_name_from_path(
            testscript, "fallback", test_dir
        )
        assert result == "nrfu.verify_device_status"

    def test_handles_nested_test_directories(self) -> None:
        """Test derivation from nested paths like templates/api/tenants/verify.py."""
        testscript = "/path/to/templates/api/tenants/verify_tenant.py"
        test_dir = Path("/path/to/templates")
        result = ArchiveInspector._derive_test_name_from_path(
            testscript, "fallback", test_dir
        )
        assert result == "api.tenants.verify_tenant"

    def test_falls_back_when_testscript_empty(self) -> None:
        """Test that fallback name is used when testscript is empty."""
        test_dir = Path("/path/to/templates")
        result = ArchiveInspector._derive_test_name_from_path(
            "", "my_fallback_name", test_dir
        )
        assert result == "my_fallback_name"

    def test_falls_back_when_path_not_under_test_dir(self) -> None:
        """Test that fallback is used when path is not under test_dir."""
        testscript = "/completely/different/path/verify.py"
        test_dir = Path("/path/to/templates")
        result = ArchiveInspector._derive_test_name_from_path(
            testscript, "fallback", test_dir
        )
        assert result == "fallback"

    def test_handles_d2d_test_paths(self) -> None:
        """Test derivation from d2d test paths."""
        testscript = "/path/to/templates/d2d/operational/verify_bgp.py"
        test_dir = Path("/path/to/templates")
        result = ArchiveInspector._derive_test_name_from_path(
            testscript, "fallback", test_dir
        )
        assert result == "d2d.operational.verify_bgp"

    def test_handles_real_world_sdwan_path(self) -> None:
        """Test with a real-world SD-WAN test path."""
        test_dir = Path(
            "/Users/atestini/Desktop/Automation/testing-for-nac/"
            "nac-sdwan-terraform/pyats"
        )
        testscript = (
            "/Users/atestini/Desktop/Automation/testing-for-nac/"
            "nac-sdwan-terraform/pyats/nrfu/verify_sdwanmanager_device_status.py"
        )
        result = ArchiveInspector._derive_test_name_from_path(
            testscript, "fallback", test_dir
        )
        assert result == "nrfu.verify_sdwanmanager_device_status"


class TestZipSlipProtection:
    """Tests for Zip Slip vulnerability protection in archive extraction."""

    def test_validate_archive_paths_rejects_path_traversal(
        self, tmp_path: Path
    ) -> None:
        """Test that path traversal in archive members raises ValueError."""
        from nac_test.pyats_core.reporting.utils.archive_security import (
            validate_archive_paths,
        )

        # Create archive with malicious path traversal
        archive_path = tmp_path / "malicious.zip"
        with zipfile.ZipFile(archive_path, "w") as zf:
            # Add a file with path traversal
            zf.writestr("../../../etc/passwd", "malicious content")

        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        with zipfile.ZipFile(archive_path, "r") as zf:
            with pytest.raises(ValueError, match="Path traversal detected"):
                validate_archive_paths(zf, extract_dir)

    def test_validate_archive_paths_accepts_safe_paths(self, tmp_path: Path) -> None:
        """Test that safe archive paths are accepted."""
        from nac_test.pyats_core.reporting.utils.archive_security import (
            validate_archive_paths,
        )

        # Create archive with safe paths
        archive_path = tmp_path / "safe.zip"
        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr("results.json", "{}")
            zf.writestr("subdir/file.txt", "content")
            zf.writestr("deeply/nested/path/file.txt", "content")

        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        with zipfile.ZipFile(archive_path, "r") as zf:
            # Should not raise
            validate_archive_paths(zf, extract_dir)

    def test_archive_extractor_rejects_malicious_archive(self, tmp_path: Path) -> None:
        """Test that ArchiveExtractor.extract_archive_to_directory rejects malicious archives."""
        from nac_test.pyats_core.reporting.utils.archive_extractor import (
            ArchiveExtractor,
        )

        # Create archive with path traversal
        archive_path = tmp_path / "malicious.zip"
        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr("../escape.txt", "escaped content")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = ArchiveExtractor.extract_archive_to_directory(
            archive_path, output_dir, f"{PYATS_RESULTS_DIRNAME}/api"
        )

        # Should return None due to security error
        assert result is None

        # Verify the escaped file was NOT created
        escaped_file = tmp_path / "escape.txt"
        assert not escaped_file.exists()
