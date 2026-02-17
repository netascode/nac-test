# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt
"""Unit tests for ACI defaults validation in CLI.

These tests verify the business logic of ACI defaults validation, ensuring
the CLI correctly detects when the defaults file is missing in ACI environments.
"""

from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch

from nac_test.cli.validators.aci_defaults import (
    _file_contains_defaults_structure,
    _path_contains_defaults_structure,
    validate_aci_defaults,
)


class TestValidateAciDefaults:
    """Tests for validate_aci_defaults function.

    This function provides a fast pre-merge check to catch the common
    mistake of forgetting to include -d ./defaults/ in the command.
    """

    def test_returns_true_when_not_aci_environment(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        """Non-ACI environment always passes the validation check."""
        monkeypatch.delenv("ACI_URL", raising=False)

        result = validate_aci_defaults([Path("./data")])

        assert result is True

    def test_returns_true_when_path_contains_defaults_directory(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        """Path with '/defaults/' directory component passes validation."""
        monkeypatch.setenv("ACI_URL", "https://apic.example.com")

        result = validate_aci_defaults(
            [
                Path("./data"),
                Path("./aac/defaults/"),
            ]
        )

        assert result is True

    def test_returns_true_when_path_ends_with_defaults(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        """Path ending with '/defaults' passes validation."""
        monkeypatch.setenv("ACI_URL", "https://apic.example.com")

        result = validate_aci_defaults([Path("/path/to/defaults")])

        assert result is True

    def test_returns_true_when_defaults_yaml_file(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        """File named 'defaults.yaml' passes validation."""
        monkeypatch.setenv("ACI_URL", "https://apic.example.com")

        result = validate_aci_defaults([Path("./defaults.yaml")])

        assert result is True

    def test_returns_true_when_defaults_nac_yaml_file(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        """File named 'defaults.nac.yaml' passes validation."""
        monkeypatch.setenv("ACI_URL", "https://apic.example.com")

        result = validate_aci_defaults([Path("./defaults.nac.yaml")])

        assert result is True

    def test_returns_false_when_aci_without_defaults_path(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        """ACI environment without defaults-like path fails validation."""
        monkeypatch.setenv("ACI_URL", "https://apic.example.com")

        result = validate_aci_defaults([Path("./data"), Path("./config")])

        assert result is False

    def test_case_insensitive_directory_matching(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        """Validation is case-insensitive for directory names."""
        monkeypatch.setenv("ACI_URL", "https://apic.example.com")

        # Uppercase should match
        result = validate_aci_defaults([Path("./DEFAULTS/")])
        assert result is True

        # Mixed case should match
        result = validate_aci_defaults([Path("./Defaults/")])
        assert result is True

    def test_handles_empty_aci_url_as_not_set(self, monkeypatch: MonkeyPatch) -> None:
        """Empty string ACI_URL is treated as not set."""
        monkeypatch.setenv("ACI_URL", "")

        result = validate_aci_defaults([Path("./data")])

        assert result is True

    def test_single_data_path_without_defaults(self, monkeypatch: MonkeyPatch) -> None:
        """Common mistake: single -d ./data without -d ./defaults/."""
        monkeypatch.setenv("ACI_URL", "https://apic.example.com")

        result = validate_aci_defaults([Path("./data")])

        assert result is False

    def test_rejects_non_yaml_file_with_default_in_name(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        """File with 'default' in name but non-YAML extension should fail heuristic."""
        monkeypatch.setenv("ACI_URL", "https://apic.example.com")

        # These should NOT pass the quick heuristic (Stage 1)
        # They would need actual defaults.apic structure in content (Stage 2)
        result = validate_aci_defaults([Path("./my-defaults-backup.txt")])
        assert result is False

        result = validate_aci_defaults([Path("./defaulted_config.json")])
        assert result is False

    def test_rejects_default_as_substring_in_directory(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        """Directory name containing 'default' as substring should not match."""
        monkeypatch.setenv("ACI_URL", "https://apic.example.com")

        # "defaultuser" is not the same as "default" or "defaults"
        result = validate_aci_defaults([Path("/users/defaultuser/workspace/config")])
        assert result is False

        # "my-defaulted-config" should not match
        result = validate_aci_defaults([Path("./my-defaulted-config/")])
        assert result is False

    def test_accepts_yaml_file_with_default_in_filename(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        """YAML file with 'default' in filename should pass heuristic."""
        monkeypatch.setenv("ACI_URL", "https://apic.example.com")

        # These should pass Stage 1 (quick heuristic)
        result = validate_aci_defaults([Path("./default.yaml")])
        assert result is True

        result = validate_aci_defaults([Path("./my-defaults.yml")])
        assert result is True

        result = validate_aci_defaults([Path("/path/to/aci-defaults.yaml")])
        assert result is True


class TestFileContainsDefaultsStructure:
    """Tests for _file_contains_defaults_structure function.

    This function uses YAML parsing to check if a file contains the
    defaults.apic structure pattern.
    """

    def test_returns_true_when_file_has_both_patterns(self, tmp_path: Path) -> None:
        """File with 'defaults:' and 'apic:' patterns returns True."""
        yaml_file = tmp_path / "defaults.yaml"
        yaml_file.write_text("defaults:\n  apic:\n    version: 5.2\n")

        result = _file_contains_defaults_structure(yaml_file)

        assert result is True

    def test_returns_false_when_missing_defaults_pattern(self, tmp_path: Path) -> None:
        """File with 'apic:' but missing 'defaults:' returns False."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("apic:\n  url: https://example.com\n")

        result = _file_contains_defaults_structure(yaml_file)

        assert result is False

    def test_returns_false_when_missing_apic_pattern(self, tmp_path: Path) -> None:
        """File with 'defaults:' but missing 'apic:' returns False."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("defaults:\n  sdwan:\n    version: 1.0\n")

        result = _file_contains_defaults_structure(yaml_file)

        assert result is False

    def test_returns_false_for_empty_file(self, tmp_path: Path) -> None:
        """Empty file returns False."""
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("")

        result = _file_contains_defaults_structure(yaml_file)

        assert result is False

    def test_returns_false_for_unreadable_file(self, tmp_path: Path) -> None:
        """File that cannot be read returns False (graceful handling)."""
        # Point to a file that doesn't exist
        nonexistent = tmp_path / "nonexistent.yaml"

        result = _file_contains_defaults_structure(nonexistent)

        assert result is False

    def test_returns_false_for_symlink(self, tmp_path: Path) -> None:
        """Symlink is rejected for security reasons."""
        # Create a real file and a symlink to it
        real_file = tmp_path / "real.yaml"
        real_file.write_text("defaults:\n  apic:\n    version: 5.2\n")
        symlink = tmp_path / "link.yaml"
        symlink.symlink_to(real_file)

        result = _file_contains_defaults_structure(symlink)

        assert result is False

    def test_returns_false_for_oversized_file(self, tmp_path: Path) -> None:
        """File larger than 3MB is skipped to prevent memory exhaustion."""
        large_file = tmp_path / "large.yaml"
        # Create a file just over 3MB (ACI YAMLs can be 2-3MB, but beyond that is suspicious)
        large_file.write_text("defaults:\n  apic:\n" + "x" * (3 * 1024 * 1024 + 100))

        result = _file_contains_defaults_structure(large_file)

        assert result is False


class TestPathContainsDefaultsStructure:
    """Tests for _path_contains_defaults_structure function.

    This function handles both files and directories, scanning YAML files
    for the defaults.apic structure pattern.
    """

    def test_returns_true_for_yaml_file_with_structure(self, tmp_path: Path) -> None:
        """YAML file containing defaults.apic structure returns True."""
        yaml_file = tmp_path / "defaults.yaml"
        yaml_file.write_text("defaults:\n  apic:\n    version: 5.2\n")

        result = _path_contains_defaults_structure(yaml_file)

        assert result is True

    def test_returns_true_for_yml_file_with_structure(self, tmp_path: Path) -> None:
        """YML file containing defaults.apic structure returns True."""
        yaml_file = tmp_path / "defaults.yml"
        yaml_file.write_text("defaults:\n  apic:\n    version: 5.2\n")

        result = _path_contains_defaults_structure(yaml_file)

        assert result is True

    def test_returns_false_for_non_yaml_file(self, tmp_path: Path) -> None:
        """Non-YAML file returns False even if it contains patterns."""
        text_file = tmp_path / "config.txt"
        text_file.write_text("defaults:\n  apic:\n    version: 5.2\n")

        result = _path_contains_defaults_structure(text_file)

        assert result is False

    def test_returns_true_for_directory_with_matching_yaml(
        self, tmp_path: Path
    ) -> None:
        """Directory containing YAML file with structure returns True."""
        yaml_file = tmp_path / "defaults.yaml"
        yaml_file.write_text("defaults:\n  apic:\n    version: 5.2\n")

        result = _path_contains_defaults_structure(tmp_path)

        assert result is True

    def test_returns_true_for_directory_with_matching_yml(self, tmp_path: Path) -> None:
        """Directory containing YML file with structure returns True."""
        yaml_file = tmp_path / "defaults.yml"
        yaml_file.write_text("defaults:\n  apic:\n    version: 5.2\n")

        result = _path_contains_defaults_structure(tmp_path)

        assert result is True

    def test_returns_false_for_directory_without_matching_files(
        self, tmp_path: Path
    ) -> None:
        """Directory without matching YAML files returns False."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("tenant:\n  name: test\n")

        result = _path_contains_defaults_structure(tmp_path)

        assert result is False

    def test_returns_false_for_empty_directory(self, tmp_path: Path) -> None:
        """Empty directory returns False."""
        result = _path_contains_defaults_structure(tmp_path)

        assert result is False

    def test_directory_scan_is_non_recursive(self, tmp_path: Path) -> None:
        """Directory scan only checks immediate children, not subdirectories.

        This is intentional for performance - deep directory traversal would
        be too slow for the pre-merge heuristic check.
        """
        # Create nested structure with defaults in subdirectory
        subdir = tmp_path / "nested"
        subdir.mkdir()
        yaml_file = subdir / "defaults.yaml"
        yaml_file.write_text("defaults:\n  apic:\n    version: 5.2\n")

        # Parent directory should NOT find the nested file
        result = _path_contains_defaults_structure(tmp_path)

        assert result is False


class TestValidateAciDefaultsContentBased:
    """Tests for content-based heuristic in validate_aci_defaults.

    These tests verify that the function correctly peeks inside YAML files
    to find the defaults.apic structure when path names don't match.
    """

    def test_returns_true_when_yaml_file_contains_defaults_structure(
        self, monkeypatch: MonkeyPatch, tmp_path: Path
    ) -> None:
        """ACI environment passes if YAML file contains defaults.apic structure."""
        monkeypatch.setenv("ACI_URL", "https://apic.example.com")

        # Create a YAML file with non-standard name but correct structure
        yaml_file = tmp_path / "my_config.yaml"
        yaml_file.write_text("defaults:\n  apic:\n    version: 5.2\n")

        result = validate_aci_defaults([yaml_file])

        assert result is True

    def test_returns_true_when_directory_contains_yaml_with_structure(
        self, monkeypatch: MonkeyPatch, tmp_path: Path
    ) -> None:
        """ACI environment passes if directory contains YAML with structure."""
        monkeypatch.setenv("ACI_URL", "https://apic.example.com")

        # Create a directory with non-standard name but contains valid defaults
        data_dir = tmp_path / "my_data"
        data_dir.mkdir()
        yaml_file = data_dir / "aci_settings.yaml"
        yaml_file.write_text("defaults:\n  apic:\n    version: 5.2\n")

        result = validate_aci_defaults([data_dir])

        assert result is True

    def test_path_check_takes_priority_over_content_check(
        self, monkeypatch: MonkeyPatch, tmp_path: Path
    ) -> None:
        """Path containing 'default' passes without content scanning.

        This tests the two-stage approach: path check is faster and runs first.
        """
        monkeypatch.setenv("ACI_URL", "https://apic.example.com")

        # Create directory with 'default' in name but NO valid YAML content
        default_dir = tmp_path / "defaults"
        default_dir.mkdir()
        # Empty directory - no YAML files to scan

        result = validate_aci_defaults([default_dir])

        assert result is True  # Passes on path name alone

    def test_content_check_runs_when_path_check_fails(
        self, monkeypatch: MonkeyPatch, tmp_path: Path
    ) -> None:
        """Content scan runs only when path-based check doesn't find 'default'."""
        monkeypatch.setenv("ACI_URL", "https://apic.example.com")

        # Create files with non-standard names
        data_dir = tmp_path / "my_aci_config"
        data_dir.mkdir()
        yaml_file = data_dir / "settings.yaml"
        yaml_file.write_text("defaults:\n  apic:\n    version: 5.2\n")

        result = validate_aci_defaults([data_dir])

        assert result is True  # Passes via content scan

    def test_returns_false_when_no_defaults_structure_found(
        self, monkeypatch: MonkeyPatch, tmp_path: Path
    ) -> None:
        """ACI environment fails if no YAML files contain defaults.apic."""
        monkeypatch.setenv("ACI_URL", "https://apic.example.com")

        # Create directory with YAML files but wrong structure
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        yaml_file = data_dir / "tenants.yaml"
        yaml_file.write_text("tenants:\n  - name: tenant1\n")

        result = validate_aci_defaults([data_dir])

        assert result is False
