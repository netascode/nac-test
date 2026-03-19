# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Tests for macOS unsupported Python version hard exit behavior.

Verifies that nac-test exits immediately on macOS with Python < 3.12.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from nac_test.cli.main import app

runner = CliRunner()


@pytest.fixture()
def cli_dirs(tmp_path: Path) -> dict[str, Path]:
    """Create the minimal directory structure required by typer's exists=True validation."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    output_dir = tmp_path / "output"
    return {
        "data_dir": data_dir,
        "templates_dir": templates_dir,
        "output_dir": output_dir,
    }


class TestMacOSUnsupportedPythonHardExit:
    """Tests for the CLI-level macOS unsupported Python hard exit gate."""

    def test_unsupported_macos_python_exits_with_error(
        self, cli_dirs: dict[str, Path]
    ) -> None:
        """CLI must exit(1) on macOS with unsupported Python before any expensive operations."""
        with (
            patch("nac_test.utils.platform.IS_UNSUPPORTED_MACOS_PYTHON", True),
            patch("nac_test.cli.main.DataMerger") as mock_merger,
            patch("nac_test.cli.main.CombinedOrchestrator") as mock_orch,
        ):
            result = runner.invoke(
                app,
                [
                    "-d",
                    str(cli_dirs["data_dir"]),
                    "-t",
                    str(cli_dirs["templates_dir"]),
                    "-o",
                    str(cli_dirs["output_dir"]),
                ],
            )

        assert result.exit_code == 1
        assert "on macOS is not supported" in result.output
        # Verify early exit: no expensive operations should be called
        mock_merger.merge_data_files.assert_not_called()
        mock_orch.assert_not_called()

    def test_unsupported_macos_python_shows_upgrade_instructions(
        self, cli_dirs: dict[str, Path]
    ) -> None:
        """Error message must include actionable upgrade instructions."""
        with patch("nac_test.utils.platform.IS_UNSUPPORTED_MACOS_PYTHON", True):
            result = runner.invoke(
                app,
                [
                    "-d",
                    str(cli_dirs["data_dir"]),
                    "-t",
                    str(cli_dirs["templates_dir"]),
                    "-o",
                    str(cli_dirs["output_dir"]),
                ],
            )

        assert "Python 3.12 or higher" in result.output
        assert "brew install python@3.12" in result.output
        assert "uv python install 3.12" in result.output
        assert "pyenv install 3.12" in result.output

    def test_supported_platform_proceeds_normally(
        self, cli_dirs: dict[str, Path]
    ) -> None:
        """Supported platforms (IS_UNSUPPORTED_MACOS_PYTHON=False) must NOT trigger the hard exit."""
        with (
            patch("nac_test.utils.platform.IS_UNSUPPORTED_MACOS_PYTHON", False),
            patch("nac_test.cli.main.DataMerger") as mock_merger,
            patch("nac_test.cli.main.CombinedOrchestrator") as mock_orch,
        ):
            mock_merger.merge_data_files.return_value = {}
            mock_instance = mock_orch.return_value
            mock_instance.run_tests.return_value = None

            result = runner.invoke(
                app,
                [
                    "-d",
                    str(cli_dirs["data_dir"]),
                    "-t",
                    str(cli_dirs["templates_dir"]),
                    "-o",
                    str(cli_dirs["output_dir"]),
                ],
            )

        assert "on macOS is not supported" not in result.output
