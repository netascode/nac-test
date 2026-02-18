# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for SubprocessRunner.

Tests the subprocess execution logic:
1. Config file content verification (git_info = false for macOS fork() safety)
2. Command construction includes all required PyATS flags
3. Error handling when config file creation fails
4. Return code interpretation (0 = success, 1 = test failures, >1 = error)
5. Output processing and progress event parsing
"""

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from nac_test.pyats_core.execution.subprocess_runner import SubprocessRunner


def _make_mock_process(
    return_code: int = 0, stdout_lines: list[bytes] | None = None
) -> AsyncMock:
    """Create a mock asyncio subprocess with configurable output.

    Args:
        return_code: The process return code.
        stdout_lines: Lines to yield from stdout. If None, empty stream.

    Returns:
        A mock process that behaves like asyncio.subprocess.Process.
    """
    process = AsyncMock()
    process.returncode = return_code

    if stdout_lines is None:
        stdout_lines = []

    line_iter = iter(stdout_lines + [b""])  # Empty bytes signals EOF
    process.stdout = AsyncMock()
    process.stdout.readline = AsyncMock(side_effect=line_iter)
    process.stdout.read = AsyncMock(return_value=b"")

    async def fake_wait() -> int:
        return return_code

    process.wait = AsyncMock(side_effect=fake_wait)
    process.communicate = AsyncMock(return_value=(b"", b""))

    return process


def _run_and_capture_cmd(
    runner: SubprocessRunner,
    method: str = "execute_job",
    return_code: int = 0,
    **method_kwargs: Any,
) -> tuple[list[str], Path | None]:
    """Run a SubprocessRunner method with mocked subprocess, capturing the command.

    Only mocks asyncio.create_subprocess_exec — lets tempfile create real files
    so config content can be verified.

    Args:
        runner: The SubprocessRunner instance.
        method: Which method to call ('execute_job' or 'execute_job_with_testbed').
        return_code: Simulated subprocess return code.
        **method_kwargs: Arguments passed to the runner method.

    Returns:
        Tuple of (captured_command_args, method_return_value).
    """
    captured_cmd: list[str] = []
    mock_process = _make_mock_process(return_code=return_code)

    with patch(
        "asyncio.create_subprocess_exec",
        new_callable=AsyncMock,
    ) as mock_exec:

        def capture(*args: Any, **kwargs: Any) -> Any:
            captured_cmd.extend(args)
            return mock_process

        mock_exec.side_effect = capture
        result = asyncio.run(getattr(runner, method)(**method_kwargs))

    return captured_cmd, result


@pytest.fixture
def runner(tmp_path: Path) -> SubprocessRunner:
    """Create a SubprocessRunner with a temp output directory."""
    return SubprocessRunner(
        output_dir=tmp_path,
        output_handler=lambda line: None,
    )


class TestConfigFileContent:
    """Tests that config files contain the correct content for macOS fork() safety."""

    def test_execute_job_writes_git_info_false_to_pyats_config(
        self, runner: SubprocessRunner
    ) -> None:
        """Verify the PyATS INI config disables git_info collection.

        The git_info setting causes fork() crashes on macOS with Python 3.12+
        due to CoreFoundation lock corruption in get_git_info(). This test
        reads the actual temp file to confirm correct content.
        """
        cmd, _ = _run_and_capture_cmd(
            runner, method="execute_job", job_file_path=Path("/fake/job.py"), env={}
        )

        config_idx = cmd.index("--pyats-configuration")
        config_path = Path(cmd[config_idx + 1])

        try:
            content = config_path.read_text()
            assert "[report]" in content
            assert "git_info = false" in content
        finally:
            config_path.unlink(missing_ok=True)

    def test_execute_job_with_testbed_writes_git_info_false_to_pyats_config(
        self, runner: SubprocessRunner
    ) -> None:
        """Verify execute_job_with_testbed also writes the correct INI content.

        Both execution paths (API and D2D) must include the macOS fork() crash fix.
        """
        cmd, _ = _run_and_capture_cmd(
            runner,
            method="execute_job_with_testbed",
            job_file_path=Path("/fake/job.py"),
            testbed_file_path=Path("/fake/testbed.yaml"),
            env={"HOSTNAME": "test-device"},
        )

        config_idx = cmd.index("--pyats-configuration")
        config_path = Path(cmd[config_idx + 1])

        try:
            content = config_path.read_text()
            assert "[report]" in content
            assert "git_info = false" in content
        finally:
            config_path.unlink(missing_ok=True)

    def test_execute_job_writes_plugin_config_with_progress_reporter(
        self, runner: SubprocessRunner
    ) -> None:
        """Verify the plugin YAML config enables the ProgressReporterPlugin."""
        cmd, _ = _run_and_capture_cmd(
            runner, method="execute_job", job_file_path=Path("/fake/job.py"), env={}
        )

        config_idx = cmd.index("--configuration")
        config_path = Path(cmd[config_idx + 1])

        try:
            content = config_path.read_text()
            assert "ProgressReporterPlugin" in content
            assert "enabled: True" in content
        finally:
            config_path.unlink(missing_ok=True)


class TestCommandConstruction:
    """Tests that the subprocess command is constructed correctly."""

    def test_execute_job_includes_all_required_flags(
        self, runner: SubprocessRunner
    ) -> None:
        """Verify execute_job command includes all essential PyATS flags."""
        cmd, _ = _run_and_capture_cmd(
            runner, method="execute_job", job_file_path=Path("/fake/job.py"), env={}
        )

        expected_flags = [
            "run",
            "job",
            "--configuration",
            "--pyats-configuration",
            "--archive-dir",
            "--archive-name",
            "--no-archive-subdir",
            "--no-mail",
            "--no-xml-report",
        ]
        for flag in expected_flags:
            assert flag in cmd, f"Missing required flag: {flag}"

    def test_execute_job_with_testbed_includes_testbed_and_config_flags(
        self, runner: SubprocessRunner
    ) -> None:
        """Verify execute_job_with_testbed passes testbed file and both config flags."""
        cmd, _ = _run_and_capture_cmd(
            runner,
            method="execute_job_with_testbed",
            job_file_path=Path("/fake/job.py"),
            testbed_file_path=Path("/fake/testbed.yaml"),
            env={"HOSTNAME": "router1"},
        )

        assert "--testbed-file" in cmd
        testbed_idx = cmd.index("--testbed-file")
        assert cmd[testbed_idx + 1] == "/fake/testbed.yaml"

        # Both config flags must be present (plugin YAML + PyATS INI)
        assert "--configuration" in cmd
        assert "--pyats-configuration" in cmd


class TestConfigCreationFailure:
    """Tests error handling when config file creation fails."""

    def test_execute_job_returns_none_on_config_failure(self, tmp_path: Path) -> None:
        """Verify execute_job returns None and does NOT launch subprocess when config fails.

        If we can't create the config files, we must not proceed with execution
        because PyATS would use default settings that cause fork() crashes on macOS.
        """
        runner = SubprocessRunner(
            output_dir=tmp_path,
            output_handler=lambda line: None,
        )

        with (
            patch(
                "tempfile.NamedTemporaryFile",
                side_effect=OSError("disk full"),
            ),
            patch(
                "asyncio.create_subprocess_exec",
                new_callable=AsyncMock,
            ) as mock_exec,
        ):
            result = asyncio.run(
                runner.execute_job(
                    job_file_path=Path("/fake/job.py"),
                    env={},
                )
            )

        assert result is None, "execute_job must return None when config creation fails"
        mock_exec.assert_not_called()

    def test_execute_job_with_testbed_returns_none_on_config_failure(
        self, tmp_path: Path
    ) -> None:
        """Verify execute_job_with_testbed returns None when config creation fails."""
        runner = SubprocessRunner(
            output_dir=tmp_path,
            output_handler=lambda line: None,
        )

        with (
            patch(
                "tempfile.NamedTemporaryFile",
                side_effect=OSError("disk full"),
            ),
            patch(
                "asyncio.create_subprocess_exec",
                new_callable=AsyncMock,
            ) as mock_exec,
        ):
            result = asyncio.run(
                runner.execute_job_with_testbed(
                    job_file_path=Path("/fake/job.py"),
                    testbed_file_path=Path("/fake/testbed.yaml"),
                    env={"HOSTNAME": "test-device"},
                )
            )

        assert result is None
        mock_exec.assert_not_called()


class TestReturnCodeHandling:
    """Tests subprocess return code interpretation."""

    def test_execute_job_returns_archive_path_on_success(
        self, runner: SubprocessRunner
    ) -> None:
        """Verify successful execution returns the archive path."""
        _, result = _run_and_capture_cmd(
            runner, method="execute_job", job_file_path=Path("/fake/job.py"), env={}
        )

        assert result is not None
        assert str(result).endswith(".zip")

    def test_execute_job_returns_archive_on_test_failure(
        self, runner: SubprocessRunner
    ) -> None:
        """Verify return code 1 (test failures) still returns archive path.

        Return code 1 means tests ran but some failed - the archive is still valid.
        """
        _, result = _run_and_capture_cmd(
            runner,
            method="execute_job",
            return_code=1,
            job_file_path=Path("/fake/job.py"),
            env={},
        )

        assert result is not None, (
            "Return code 1 (test failures) should still return archive path"
        )

    def test_execute_job_returns_none_on_execution_error(
        self, runner: SubprocessRunner
    ) -> None:
        """Verify return code > 1 (execution error) returns None.

        Return code > 1 means PyATS itself failed, not just individual tests.
        """
        _, result = _run_and_capture_cmd(
            runner,
            method="execute_job",
            return_code=2,
            job_file_path=Path("/fake/job.py"),
            env={},
        )

        assert result is None, "Return code > 1 (execution error) should return None"


class TestProgressEventParsing:
    """Tests the NAC_PROGRESS event parsing logic."""

    @pytest.fixture
    def parser(self, tmp_path: Path) -> SubprocessRunner:
        """Create a runner used only for its _parse_progress_event method."""
        return SubprocessRunner(
            output_dir=tmp_path,
            output_handler=lambda line: None,
        )

    def test_parse_valid_progress_event(self, parser: SubprocessRunner) -> None:
        """Verify valid NAC_PROGRESS JSON lines are parsed correctly."""
        event = parser._parse_progress_event(
            'NAC_PROGRESS:{"event": "task_start", "name": "verify_tenant"}'
        )

        assert event is not None
        assert event["event"] == "task_start"
        assert event["name"] == "verify_tenant"

    def test_parse_stream_complete_sentinel(self, parser: SubprocessRunner) -> None:
        """Verify the stream_complete sentinel event is parsed."""
        event = parser._parse_progress_event(
            'NAC_PROGRESS:{"event": "stream_complete"}'
        )

        assert event is not None
        assert event["event"] == "stream_complete"

    def test_non_progress_line_returns_none(self, parser: SubprocessRunner) -> None:
        """Verify regular output lines are not parsed as progress events."""
        assert parser._parse_progress_event("Some regular output") is None
        assert parser._parse_progress_event("") is None
        assert parser._parse_progress_event("NAC_PROGRES:almost") is None

    def test_malformed_json_returns_none(self, parser: SubprocessRunner) -> None:
        """Verify malformed JSON after NAC_PROGRESS: prefix returns None."""
        assert parser._parse_progress_event("NAC_PROGRESS:{bad json}") is None
        assert parser._parse_progress_event("NAC_PROGRESS:") is None


class TestOutputProcessing:
    """Tests output handling and sentinel-based synchronization."""

    def test_output_handler_receives_all_lines(self, tmp_path: Path) -> None:
        """Verify the output handler receives each line from subprocess stdout."""
        received_lines: list[str] = []

        mock_process = _make_mock_process(
            return_code=0,
            stdout_lines=[
                b"Starting tests...\n",
                b'NAC_PROGRESS:{"event": "task_start"}\n',
                b"Test passed\n",
                b'NAC_PROGRESS:{"event": "stream_complete"}\n',
            ],
        )

        runner = SubprocessRunner(
            output_dir=tmp_path,
            output_handler=received_lines.append,
        )

        asyncio.run(runner._process_output_realtime(mock_process))

        assert len(received_lines) == 4
        assert "Starting tests..." in received_lines[0]
        assert "NAC_PROGRESS:" in received_lines[1]

    def test_sentinel_prevents_legacy_drain(self, tmp_path: Path) -> None:
        """Verify stream_complete sentinel skips the legacy buffer drain.

        When the progress plugin emits a stream_complete sentinel, the
        runner should NOT call the legacy drain method since all data
        has been received reliably via the sentinel protocol.
        """
        mock_process = _make_mock_process(
            return_code=0,
            stdout_lines=[
                b"Test output\n",
                b'NAC_PROGRESS:{"event": "stream_complete"}\n',
            ],
        )

        runner = SubprocessRunner(
            output_dir=tmp_path,
            output_handler=lambda line: None,
        )

        with patch.object(
            runner, "_drain_remaining_buffer_safe", new_callable=AsyncMock
        ) as mock_drain:
            asyncio.run(runner._process_output_realtime(mock_process))

        mock_drain.assert_not_called()

    def test_no_sentinel_triggers_legacy_drain(self, tmp_path: Path) -> None:
        """Verify missing sentinel triggers the legacy buffer drain.

        Backward compatibility: older plugins that don't emit stream_complete
        should still get their remaining buffer data drained.
        """
        mock_process = _make_mock_process(
            return_code=0,
            stdout_lines=[
                b"Test output\n",
            ],
        )

        runner = SubprocessRunner(
            output_dir=tmp_path,
            output_handler=lambda line: None,
        )

        with patch.object(
            runner, "_drain_remaining_buffer_safe", new_callable=AsyncMock
        ) as mock_drain:
            asyncio.run(runner._process_output_realtime(mock_process))

        mock_drain.assert_called_once()
