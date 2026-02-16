# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for SubprocessRunner initialization.

This module tests the pyats executable resolution logic in SubprocessRunner.__init__().
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nac_test.pyats_core.execution.subprocess_runner import SubprocessRunner


class TestSubprocessRunnerInit:
    """Test suite for SubprocessRunner.__init__() pyats executable resolution."""

    def test_resolves_pyats_using_sysconfig(self, tmp_path: Path) -> None:
        """Test that pyats executable is resolved using sysconfig.get_path('scripts')."""
        fake_scripts_dir = tmp_path / "scripts"
        fake_scripts_dir.mkdir()
        fake_pyats_executable = fake_scripts_dir / "pyats"
        fake_pyats_executable.touch()

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        output_handler = MagicMock()

        with patch("sysconfig.get_path", return_value=str(fake_scripts_dir)):
            runner = SubprocessRunner(
                output_dir=output_dir,
                output_handler=output_handler,
            )

        assert runner.pyats_executable == str(fake_pyats_executable)

    def test_raises_runtime_error_when_pyats_not_found(self, tmp_path: Path) -> None:
        """Test that RuntimeError is raised when pyats executable does not exist."""
        fake_scripts_dir = tmp_path / "scripts"
        fake_scripts_dir.mkdir()

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        output_handler = MagicMock()

        with patch("sysconfig.get_path", return_value=str(fake_scripts_dir)):
            with pytest.raises(RuntimeError, match="pyats executable not found"):
                SubprocessRunner(
                    output_dir=output_dir,
                    output_handler=output_handler,
                )

    def test_does_not_use_sys_executable(self, tmp_path: Path) -> None:
        """Test that sys.executable is NOT accessed (regression prevention).

        This test verifies we don't revert to the old sys.executable.parent logic.
        """
        fake_scripts_dir = tmp_path / "scripts"
        fake_scripts_dir.mkdir()
        fake_pyats_executable = fake_scripts_dir / "pyats"
        fake_pyats_executable.touch()

        output_dir = tmp_path / "output"
        output_dir.mkdir()
        output_handler = MagicMock()

        with patch("sysconfig.get_path", return_value=str(fake_scripts_dir)):
            with patch("sys.executable", new=MagicMock()) as mock_sys_executable:
                runner = SubprocessRunner(
                    output_dir=output_dir,
                    output_handler=output_handler,
                )

        mock_sys_executable.assert_not_called()
        assert runner.pyats_executable == str(fake_pyats_executable)
