# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Template rendering tests for nac-test CLI.

This module contains integration tests that verify template rendering
functionality including render-only mode, list rendering variations,
chunked rendering, and merged data model output.
"""

import filecmp
import os
from pathlib import Path

import pytest
import yaml  # type: ignore
from typer.testing import CliRunner

import nac_test.cli.main

pytestmark = pytest.mark.integration


def verify_file_content(expected_yaml_path: Path, output_dir: Path) -> None:
    """Verify that files in output_dir match the expected content from YAML.

    Args:
        expected_yaml_path: Path to YAML file with structure {filename: content}.
        output_dir: Base directory where the files should exist.

    Raises:
        AssertionError: If any file content doesn't match expected content.
    """
    with open(expected_yaml_path) as f:
        expected_files = yaml.safe_load(f)

    for filename, expected_content in expected_files.items():
        file_path = output_dir / filename
        assert file_path.exists(), f"Expected file does not exist: {file_path}"

        actual_content = file_path.read_text()
        assert actual_content.strip() == expected_content.strip(), (
            f"Content mismatch in {filename}:\n"
            f"Expected:\n{expected_content}\n"
            f"Actual:\n{actual_content}"
        )


def test_render_only_mode_succeeds_with_valid_templates(tmp_path: Path) -> None:
    """Test that render-only mode succeeds with valid template files.

    Verifies that the --render-only flag causes nac-test to render
    templates without executing any tests.

    Args:
        tmp_path: Pytest fixture providing a temporary directory.
    """
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data/"
    templates_path = "tests/integration/fixtures/templates_fail/"
    result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            data_path,
            "-t",
            templates_path,
            "-o",
            str(tmp_path),
            "--render-only",
        ],
    )
    assert result.exit_code == 0, (
        f"Render-only mode should succeed with valid templates, got exit code "
        f"{result.exit_code}: {result.output}"
    )


def test_render_only_mode_fails_with_missing_template_variables(
    tmp_path: Path,
) -> None:
    """Test that render-only mode fails when template variables are missing.

    Verifies that the CLI properly reports an error when templates
    reference variables not present in the data files.

    Args:
        tmp_path: Pytest fixture providing a temporary directory.
    """
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data/"
    templates_path = "tests/integration/fixtures/templates_missing/"
    result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            data_path,
            "-t",
            templates_path,
            "-o",
            str(tmp_path),
            "--render-only",
        ],
    )
    assert result.exit_code == 1, (
        f"Render-only mode should fail with missing variables, got exit code "
        f"{result.exit_code}: {result.output}"
    )


def test_render_only_mode_succeeds_with_default_filter_for_missing_variables(
    tmp_path: Path,
) -> None:
    """Test that render-only mode succeeds when missing variables have defaults.

    Verifies that templates using Jinja default filters for missing
    variables render successfully without errors.

    Args:
        tmp_path: Pytest fixture providing a temporary directory.
    """
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data/"
    templates_path = "tests/integration/fixtures/templates_missing_default/"
    result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            data_path,
            "-t",
            templates_path,
            "-o",
            str(tmp_path),
            "--render-only",
        ],
    )
    assert result.exit_code == 0, (
        f"Render-only mode should succeed with default filter, got exit code "
        f"{result.exit_code}: {result.output}"
    )


def test_list_rendering_creates_device_folders(tmp_path: Path) -> None:
    """Test that list rendering creates separate folders per device.

    Verifies that when rendering templates over a list of items,
    the CLI creates a separate folder for each item containing
    the rendered template file.

    Args:
        tmp_path: Pytest fixture providing a temporary directory.
    """
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data_list/"
    templates_path = "tests/integration/fixtures/templates_list/"
    result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            data_path,
            "-t",
            templates_path,
            "-o",
            str(tmp_path),
            "--render-only",
        ],
    )
    assert (tmp_path / "ABC" / "test1.robot").exists(), (
        "Expected device folder ABC/test1.robot to be created"
    )
    assert (tmp_path / "DEF" / "test1.robot").exists(), (
        "Expected device folder DEF/test1.robot to be created"
    )
    assert (tmp_path / "_abC" / "test1.robot").exists(), (
        "Expected device folder _abC/test1.robot to be created"
    )
    assert result.exit_code == 0, (
        f"List rendering should succeed, got exit code {result.exit_code}: "
        f"{result.output}"
    )


def test_list_rendering_creates_device_files_in_shared_folder(tmp_path: Path) -> None:
    """Test that list rendering can create separate files per device in one folder.

    Verifies that when rendering templates over a list with folder mode,
    the CLI creates a single folder containing a separate file for each item.

    Args:
        tmp_path: Pytest fixture providing a temporary directory.
    """
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data_list/"
    templates_path = "tests/integration/fixtures/templates_list_folder/"
    result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            data_path,
            "-t",
            templates_path,
            "-o",
            str(tmp_path),
            "--render-only",
        ],
    )
    assert (tmp_path / "test1" / "ABC.robot").exists(), (
        "Expected device file test1/ABC.robot to be created"
    )
    assert (tmp_path / "test1" / "DEF.robot").exists(), (
        "Expected device file test1/DEF.robot to be created"
    )
    assert (tmp_path / "test1" / "_abC.robot").exists(), (
        "Expected device file test1/_abC.robot to be created"
    )
    assert result.exit_code == 0, (
        f"List rendering with folder mode should succeed, got exit code "
        f"{result.exit_code}: {result.output}"
    )


def test_chunked_list_rendering_produces_expected_content(tmp_path: Path) -> None:
    """Test that chunked list rendering produces correctly chunked output files.

    Verifies that when rendering templates with chunked iteration,
    the CLI creates output files with content split into the expected
    chunks matching the expected_content.yaml specification.

    Args:
        tmp_path: Pytest fixture providing a temporary directory.
    """
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data_list_chunked/"
    templates_path = "tests/integration/fixtures/templates_list_chunked/"
    result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            data_path,
            "-t",
            templates_path,
            "-o",
            str(tmp_path),
            "--render-only",
        ],
    )
    assert result.exit_code == 0, (
        f"Chunked list rendering should succeed, got exit code {result.exit_code}: "
        f"{result.output}"
    )
    assert not (tmp_path / "ABC" / "test1.robot").exists(), (
        "Chunked rendering should not create individual device folders"
    )
    assert not (tmp_path / "DEF" / "test1.robot").exists(), (
        "Chunked rendering should not create individual device folders"
    )
    # Verify files and their content match expected content
    verify_file_content(Path(templates_path) / "expected_content.yaml", tmp_path)


def test_merged_data_model_creates_default_filename(tmp_path: Path) -> None:
    """Test that merged data model creates file with default filename.

    Verifies that the CLI creates a merged data model YAML file with
    the default filename when no custom filename is specified.

    Args:
        tmp_path: Pytest fixture providing a temporary directory.
    """
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data_merge/"
    templates_path = "tests/integration/fixtures/templates/"
    expected_filename = "merged_data_model_test_variables.yaml"
    output_model_path = tmp_path / expected_filename
    expected_model_path = "tests/integration/fixtures/data_merge/result.yaml"

    base_args = [
        "-d",
        os.path.join(data_path, "file1.yaml"),
        "-d",
        os.path.join(data_path, "file2.yaml"),
        "-t",
        templates_path,
        "-o",
        str(tmp_path),
        "--render-only",
    ]

    result = runner.invoke(nac_test.cli.main.app, base_args)
    assert result.exit_code == 0, (
        f"Merged data model creation should succeed, got exit code "
        f"{result.exit_code}: {result.output}"
    )
    assert output_model_path.exists(), (
        f"Default merged data model file should exist at {output_model_path}"
    )
    assert filecmp.cmp(output_model_path, expected_model_path, shallow=False), (
        f"Merged data model content should match expected content from "
        f"{expected_model_path}"
    )


def test_merged_data_model_creates_custom_filename(tmp_path: Path) -> None:
    """Test that merged data model creates file with custom filename.

    Verifies that the CLI creates a merged data model YAML file with
    a custom filename when --merged-data-filename is specified.

    Args:
        tmp_path: Pytest fixture providing a temporary directory.
    """
    runner = CliRunner()
    data_path = "tests/integration/fixtures/data_merge/"
    templates_path = "tests/integration/fixtures/templates/"
    expected_filename = "custom.yaml"
    output_model_path = tmp_path / expected_filename
    expected_model_path = "tests/integration/fixtures/data_merge/result.yaml"

    base_args = [
        "-d",
        os.path.join(data_path, "file1.yaml"),
        "-d",
        os.path.join(data_path, "file2.yaml"),
        "-t",
        templates_path,
        "-o",
        str(tmp_path),
        "--render-only",
        "--merged-data-filename",
        "custom.yaml",
    ]

    result = runner.invoke(nac_test.cli.main.app, base_args)
    assert result.exit_code == 0, (
        f"Merged data model with custom filename should succeed, got exit code "
        f"{result.exit_code}: {result.output}"
    )
    assert output_model_path.exists(), (
        f"Custom merged data model file should exist at {output_model_path}"
    )
    assert filecmp.cmp(output_model_path, expected_model_path, shallow=False), (
        f"Custom merged data model content should match expected content from "
        f"{expected_model_path}"
    )


def test_render_only_without_controller_credentials(tmp_path: Path) -> None:
    """Render-only mode works without controller environment variables.
    All other tests in this module implicitly also test this, but this
    is important enough that it warrants an explicit test.
    """
    data_file = tmp_path / "data.yaml"
    data_file.write_text("device: Router1\nip: 192.168.1.1")

    template = tmp_path / "templates" / "test.robot"
    template.parent.mkdir(parents=True)
    template.write_text(
        "*** Test Cases ***\nVerify {{ device }}\n    Log    IP: {{ ip }}"
    )

    runner = CliRunner()
    result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            str(data_file),
            "-t",
            str(template.parent),
            "-o",
            str(tmp_path / "output"),
            "--render-only",
        ],
    )

    assert result.exit_code == 0
    output = (tmp_path / "output" / "test.robot").read_text()
    assert "Verify Router1" in output
    assert "{{" not in output
