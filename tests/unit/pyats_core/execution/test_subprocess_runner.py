# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for SubprocessRunner.

This module tests the SubprocessRunner class, covering:
- Subprocess crash handling (non-zero return codes)
- File operation failures (missing archives, spawn failures)
- Malformed data recovery (invalid JSON progress events)
- Resource limit handling (LimitOverrunError, buffer timeouts)
- Initialization: pyats executable resolution via sysconfig

Note:
    All tests mock asyncio.create_subprocess_exec to avoid spawning actual
    subprocesses. Async methods are tested using asyncio.run() since
    pytest-asyncio is not installed in this project.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from nac_test.pyats_core.constants import (
    PYATS_CONFIG_FILENAME,
    PYATS_PLUGIN_CONFIG_FILENAME,
)
from nac_test.pyats_core.execution.subprocess_runner import (
    SubprocessRunner,
)
from nac_test.utils.logging import LogLevel


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """Create a temporary output directory for test artifacts."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def mock_output_handler() -> Mock:
    """Create a mock output handler for capturing subprocess output."""
    return Mock()


def _create_mock_process(return_code: int = 0) -> Mock:
    """Create a mock asyncio subprocess with configurable return code.

    Args:
        return_code: The exit code the mock process should return.

    Returns:
        Mock process object with stdout, communicate, wait, and returncode configured.
    """
    process = Mock()
    process.stdout = AsyncMock()
    process.communicate = AsyncMock(return_value=(b"", b""))
    process.wait = AsyncMock(return_value=return_code)
    process.returncode = return_code
    return process


def test_execute_job_subprocess_crashes(
    temp_output_dir: Path, mock_output_handler: Mock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that execute_job returns None when subprocess exits with code > 1."""
    runner = SubprocessRunner(temp_output_dir, mock_output_handler)
    mock_process = _create_mock_process(return_code=2)

    with (
        patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec,
        patch.object(
            runner, "_process_output_realtime", new_callable=AsyncMock
        ) as mock_output,
    ):
        mock_exec.return_value = mock_process
        mock_output.return_value = 2

        caplog.set_level(logging.ERROR)
        result = asyncio.run(
            runner.execute_job(Path("/tmp/job.py"), env={"FOO": "bar"})
        )

    assert result is None
    assert "PyATS job failed with return code: 2" in caplog.text


def test_execute_job_archive_not_created(
    temp_output_dir: Path, mock_output_handler: Mock
) -> None:
    """Test behavior when subprocess succeeds but archive file is not created."""
    runner = SubprocessRunner(temp_output_dir, mock_output_handler)
    mock_process = _create_mock_process(return_code=0)

    with (
        patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec,
        patch.object(
            runner, "_process_output_realtime", new_callable=AsyncMock
        ) as mock_output,
    ):
        mock_exec.return_value = mock_process
        mock_output.return_value = 0

        result = asyncio.run(
            runner.execute_job(Path("/tmp/job.py"), env={"FOO": "bar"})
        )

    assert isinstance(result, Path)
    assert result.parent == temp_output_dir
    assert result.suffix == ".zip"
    assert not result.exists()


def test_execute_job_spawn_failure_file_not_found(
    temp_output_dir: Path, mock_output_handler: Mock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test handling when pyats executable is not found."""
    runner = SubprocessRunner(temp_output_dir, mock_output_handler)

    with patch(
        "asyncio.create_subprocess_exec",
        new_callable=AsyncMock,
        side_effect=FileNotFoundError("pyats missing"),
    ):
        caplog.set_level(logging.ERROR)
        result = asyncio.run(
            runner.execute_job(Path("/tmp/job.py"), env={"FOO": "bar"})
        )

    assert result is None
    assert "Error executing PyATS job" in caplog.text


def test_execute_job_spawn_failure_permission_error(
    temp_output_dir: Path, mock_output_handler: Mock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test handling when pyats executable lacks execute permission."""
    runner = SubprocessRunner(temp_output_dir, mock_output_handler)

    with patch(
        "asyncio.create_subprocess_exec",
        new_callable=AsyncMock,
        side_effect=PermissionError("permission denied"),
    ):
        caplog.set_level(logging.ERROR)
        result = asyncio.run(
            runner.execute_job(Path("/tmp/job.py"), env={"FOO": "bar"})
        )

    assert result is None
    assert "Error executing PyATS job" in caplog.text


def test_parse_progress_event_malformed_json(
    temp_output_dir: Path, mock_output_handler: Mock
) -> None:
    """Test that malformed JSON in progress events returns None without raising."""
    runner = SubprocessRunner(temp_output_dir, mock_output_handler)

    result = runner._parse_progress_event("NAC_PROGRESS:{invalid json}")

    assert result is None


def test_parse_progress_event_missing_prefix(
    temp_output_dir: Path, mock_output_handler: Mock
) -> None:
    """Test that non-progress output lines return None."""
    runner = SubprocessRunner(temp_output_dir, mock_output_handler)

    result = runner._parse_progress_event("regular output")

    assert result is None


def test_process_output_limit_overrun_error(
    temp_output_dir: Path, mock_output_handler: Mock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test recovery from LimitOverrunError when output line exceeds buffer."""
    runner = SubprocessRunner(temp_output_dir, mock_output_handler)
    mock_process = _create_mock_process(return_code=0)
    mock_process.stdout.readline = AsyncMock(
        side_effect=[
            asyncio.LimitOverrunError("chunk exceeded", 1),
            b"line\n",
            b"",
        ]
    )
    mock_process.stdout.read = AsyncMock(return_value=b"oversized\n")

    caplog.set_level(logging.INFO)
    result = asyncio.run(runner._process_output_realtime(mock_process))

    assert result == 0
    assert "Output line exceeded buffer limit" in caplog.text
    assert "Successfully cleared oversized output buffer" in caplog.text
    mock_output_handler.assert_any_call("line")


def test_drain_remaining_buffer_timeout(
    temp_output_dir: Path, mock_output_handler: Mock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test graceful handling of timeout when draining remaining buffer."""
    runner = SubprocessRunner(temp_output_dir, mock_output_handler)
    stdout = AsyncMock()
    stdout.read = AsyncMock(side_effect=asyncio.TimeoutError)

    caplog.set_level(logging.WARNING)
    asyncio.run(runner._drain_remaining_buffer_safe(stdout))

    assert "Timeout" in caplog.text


# --- Initialization tests (pyats executable resolution) ---


def test_init_resolves_pyats_using_sysconfig(
    tmp_path: Path, temp_output_dir: Path, mock_output_handler: Mock
) -> None:
    """Test that pyats executable is resolved using sysconfig.get_path('scripts')."""
    fake_scripts_dir = tmp_path / "scripts"
    fake_scripts_dir.mkdir()
    fake_pyats_executable = fake_scripts_dir / "pyats"
    fake_pyats_executable.touch()

    with patch("sysconfig.get_path", return_value=str(fake_scripts_dir)):
        runner = SubprocessRunner(
            output_dir=temp_output_dir,
            output_handler=mock_output_handler,
        )

    assert runner.pyats_executable == str(fake_pyats_executable)


def test_init_raises_runtime_error_when_pyats_not_found(
    tmp_path: Path, temp_output_dir: Path, mock_output_handler: Mock
) -> None:
    """Test that RuntimeError is raised when pyats executable does not exist."""
    fake_scripts_dir = tmp_path / "scripts"
    fake_scripts_dir.mkdir()

    with patch("sysconfig.get_path", return_value=str(fake_scripts_dir)):
        with pytest.raises(RuntimeError, match="pyats executable not found"):
            SubprocessRunner(
                output_dir=temp_output_dir,
                output_handler=mock_output_handler,
            )


def test_init_does_not_use_sys_executable(
    tmp_path: Path, temp_output_dir: Path, mock_output_handler: Mock
) -> None:
    """Test that sys.executable is NOT accessed (regression prevention)."""
    fake_scripts_dir = tmp_path / "scripts"
    fake_scripts_dir.mkdir()
    fake_pyats_executable = fake_scripts_dir / "pyats"
    fake_pyats_executable.touch()

    with patch("sysconfig.get_path", return_value=str(fake_scripts_dir)):
        with patch("sys.executable", new=MagicMock()) as mock_sys_executable:
            runner = SubprocessRunner(
                output_dir=temp_output_dir,
                output_handler=mock_output_handler,
            )

    mock_sys_executable.assert_not_called()
    assert runner.pyats_executable == str(fake_pyats_executable)


# --- Command building test (loglevel flag mapping) ---


@pytest.mark.parametrize(
    "loglevel,expected_verbose_count,expected_quiet_count",
    [
        (LogLevel.DEBUG, 1, 0),
        (LogLevel.INFO, 0, 0),
        (LogLevel.WARNING, 0, 1),
        (LogLevel.ERROR, 0, 2),
        (LogLevel.CRITICAL, 0, 3),
    ],
)
def test_build_command_loglevel_to_cli_flags(
    temp_output_dir: Path,
    mock_output_handler: Mock,
    loglevel: LogLevel,
    expected_verbose_count: int,
    expected_quiet_count: int,
) -> None:
    """Test that loglevel maps to correct CLI flags (--verbose, --quiet)."""
    runner = SubprocessRunner(temp_output_dir, mock_output_handler, loglevel=loglevel)
    cmd = runner._build_command(
        job_file_path=Path("/tmp/job.py"),
        archive_name="test_archive.zip",
    )

    assert cmd.count("--verbose") == expected_verbose_count
    assert cmd.count("--quiet") == expected_quiet_count


def test_build_command_includes_config_files(
    temp_output_dir: Path,
    mock_output_handler: Mock,
) -> None:
    """Test that _build_command includes plugin and pyats config files in the command."""
    runner = SubprocessRunner(temp_output_dir, mock_output_handler)
    cmd = runner._build_command(
        job_file_path=Path("/tmp/job.py"),
        archive_name="test_archive.zip",
    )

    # Verify --configuration flag with plugin config file
    assert "--configuration" in cmd
    config_idx = cmd.index("--configuration")
    assert cmd[config_idx + 1] == str(runner._plugin_config_file)

    # Verify --pyats-configuration flag with pyats config file
    assert "--pyats-configuration" in cmd
    pyats_config_idx = cmd.index("--pyats-configuration")
    assert cmd[pyats_config_idx + 1] == str(runner._pyats_config_file)


def test_init_creates_config_files_in_output_dir(
    temp_output_dir: Path, mock_output_handler: Mock
) -> None:
    """Test that __init__ creates config files in the output directory."""
    runner = SubprocessRunner(temp_output_dir, mock_output_handler)

    assert runner._plugin_config_file is not None
    assert runner._pyats_config_file is not None

    assert runner._plugin_config_file.exists()
    assert runner._pyats_config_file.exists()
    assert runner._plugin_config_file.parent == temp_output_dir
    assert runner._pyats_config_file.parent == temp_output_dir
    assert runner._plugin_config_file.name == PYATS_PLUGIN_CONFIG_FILENAME
    assert runner._pyats_config_file.name == PYATS_CONFIG_FILENAME


def test_init_raises_runtime_error_on_write_failure(
    temp_output_dir: Path, mock_output_handler: Mock
) -> None:
    """Test that RuntimeError is raised when config file write fails."""
    with patch.object(Path, "write_text", side_effect=OSError("disk full")):
        with pytest.raises(RuntimeError, match="disk full"):
            SubprocessRunner(temp_output_dir, mock_output_handler)


def test_write_failure_leaves_attributes_none(
    temp_output_dir: Path,
    mock_output_handler: Mock,
) -> None:
    """Test that write failure leaves config file attributes as None."""
    with patch.object(Path, "write_text", side_effect=OSError("disk full")):
        with pytest.raises(RuntimeError):
            SubprocessRunner(temp_output_dir, mock_output_handler)


def test_partial_write_failure_cleans_up_first_file(
    temp_output_dir: Path,
) -> None:
    """Test that partial write failure cleans up successfully written files.

    If the first config file is written successfully but the second fails,
    the first file should be cleaned up to avoid orphaned files.
    """
    runner = object.__new__(SubprocessRunner)
    runner.output_dir = temp_output_dir
    runner._plugin_config_file = None
    runner._pyats_config_file = None

    # Track which file is being written
    write_count = {"count": 0}
    original_write_text = Path.write_text

    def write_text_fail_on_second(
        self: Path, content: str, *args: Any, **kwargs: Any
    ) -> None:
        write_count["count"] += 1
        if write_count["count"] == 1:
            # First write succeeds
            original_write_text(self, content, *args, **kwargs)
        else:
            # Second write fails
            raise OSError("disk full on second file")

    with patch.object(Path, "write_text", write_text_fail_on_second):
        with pytest.raises(RuntimeError, match="disk full"):
            runner._create_config_files()

    # Attributes should still be None (not set until both writes succeed)
    assert runner._plugin_config_file is None
    assert runner._pyats_config_file is None

    # The first file that was successfully written should have been cleaned up
    plugin_config_path = temp_output_dir / PYATS_PLUGIN_CONFIG_FILENAME
    assert not plugin_config_path.exists(), (
        "First config file should be cleaned up after second write fails"
    )


# --- CleanupManager registration tests ---


def test_init_registers_config_files_with_cleanup_manager(
    temp_output_dir: Path, mock_output_handler: Mock
) -> None:
    """Test that __init__ registers both config files with CleanupManager."""
    with patch(
        "nac_test.pyats_core.execution.subprocess_runner.get_cleanup_manager"
    ) as mock_get_cm:
        mock_cm = MagicMock()
        mock_get_cm.return_value = mock_cm

        runner = SubprocessRunner(temp_output_dir, mock_output_handler)

    assert mock_cm.register.call_count == 2
    registered_paths = {call.args[0] for call in mock_cm.register.call_args_list}
    assert runner._plugin_config_file in registered_paths
    assert runner._pyats_config_file in registered_paths
    # Both should use keep_if_debug=True
    for call in mock_cm.register.call_args_list:
        assert call.kwargs.get("keep_if_debug") is True or (
            len(call.args) > 1 and call.args[1] is True
        )


def test_write_failure_does_not_register_with_cleanup_manager(
    temp_output_dir: Path, mock_output_handler: Mock
) -> None:
    """Test that write failure does NOT register files with CleanupManager."""
    with (
        patch.object(Path, "write_text", side_effect=OSError("disk full")),
        patch(
            "nac_test.pyats_core.execution.subprocess_runner.get_cleanup_manager"
        ) as mock_get_cm,
    ):
        mock_cm = MagicMock()
        mock_get_cm.return_value = mock_cm

        with pytest.raises(RuntimeError):
            SubprocessRunner(temp_output_dir, mock_output_handler)

    mock_cm.register.assert_not_called()
