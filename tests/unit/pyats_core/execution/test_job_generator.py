# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for JobGenerator."""

import ast
from collections.abc import Callable
from pathlib import Path

import pytest

from nac_test.pyats_core.execution.job_generator import JobGenerator
from nac_test.utils.logging import LogLevel


class TestJobGeneratorInit:
    """Tests for JobGenerator initialization."""

    def test_pyats_managed_handlers_import(self) -> None:
        """Verify pyats.log.managed_handlers is importable and has screen attribute.
        Makes sure we notice if pyats changes their logging structure in a way that
        would break our generated job files."""
        from pyats.log import managed_handlers

        assert hasattr(managed_handlers, "screen")
        assert hasattr(managed_handlers.screen, "setLevel")


class BaseJobFileContentTests:
    """Base class with shared tests for both job file generation methods.

    Subclasses must define the `generate_content` fixture that returns a callable
    to generate job file content for the specific method being tested.
    """

    @pytest.fixture
    def generate_content(self, tmp_path: Path) -> Callable[[list[Path]], str]:
        """Return a callable that generates job file content.

        Must be overridden by subclasses.
        """
        raise NotImplementedError

    @pytest.fixture
    def default_test_files(self) -> list[Path]:
        """Default test files for tests that don't care about specific paths."""
        return [Path("/tmp/test.py")]

    def test_generates_valid_python(
        self,
        generate_content: Callable[[list[Path]], str],
        default_test_files: list[Path],
    ) -> None:
        """Test that generated job file is syntactically valid Python."""
        content = generate_content(default_test_files)
        ast.parse(content)  # Raises SyntaxError if invalid

    @pytest.mark.parametrize(
        ("loglevel", "expected_logging_expr"),
        [
            (LogLevel.DEBUG, "logging.DEBUG"),
            (LogLevel.INFO, "logging.INFO"),
            (LogLevel.WARNING, "logging.WARNING"),
            (LogLevel.ERROR, "logging.ERROR"),
            (LogLevel.CRITICAL, "logging.CRITICAL"),
        ],
    )
    def test_loglevel_mapped_to_screen_handler(
        self,
        generate_content: Callable[..., str],
        default_test_files: list[Path],
        loglevel: LogLevel,
        expected_logging_expr: str,
    ) -> None:
        """Test that loglevel is correctly used in screen handler setLevel."""
        content = generate_content(default_test_files, loglevel)
        assert f"managed_handlers.screen.setLevel({expected_logging_expr})" in content

    def test_converts_relative_paths_to_absolute(
        self,
        generate_content: Callable[[list[Path]], str],
    ) -> None:
        """Test that relative test file paths are converted to absolute paths."""
        relative_paths = [Path("test1.py"), Path("subdir/test2.py")]

        content = generate_content(relative_paths)

        for rel_path in relative_paths:
            assert str(rel_path.resolve()) in content


class TestGenerateJobFileContent(BaseJobFileContentTests):
    """Tests for generate_job_file_content (API tests)."""

    @pytest.fixture
    def generate_content(self, tmp_path: Path) -> Callable[[list[Path]], str]:
        """Return callable that generates API job file content."""

        def _generate(
            test_files: list[Path],
            loglevel: LogLevel = LogLevel.WARNING,
        ) -> str:
            generator = JobGenerator(
                max_workers=4,
                output_dir=tmp_path,
                loglevel=loglevel,
            )
            return generator.generate_job_file_content(test_files)

        return _generate

    def test_contains_max_workers(
        self, tmp_path: Path, default_test_files: list[Path]
    ) -> None:
        """Test that max_workers is set in generated job file."""
        generator = JobGenerator(
            max_workers=8, output_dir=tmp_path, loglevel=LogLevel.WARNING
        )

        content = generator.generate_job_file_content(default_test_files)

        assert "runtime.max_workers = 8" in content


class TestGenerateDeviceCentricJob(BaseJobFileContentTests):
    """Tests for generate_device_centric_job (D2D tests)."""

    @pytest.fixture
    def sample_device(self) -> dict[str, str]:
        """Create a sample device dictionary for testing."""
        return {
            "hostname": "test-router-01",
            "ip": "192.168.1.1",
            "platform": "ios",
        }

    @pytest.fixture
    def generate_content(
        self, tmp_path: Path, sample_device: dict[str, str]
    ) -> Callable[[list[Path]], str]:
        """Return callable that generates D2D job file content."""

        def _generate(
            test_files: list[Path],
            loglevel: LogLevel = LogLevel.WARNING,
        ) -> str:
            generator = JobGenerator(
                max_workers=4,
                output_dir=tmp_path,
                loglevel=loglevel,
            )
            return generator.generate_device_centric_job(sample_device, test_files)

        return _generate

    def test_contains_hostname(
        self,
        generate_content: Callable[[list[Path]], str],
        default_test_files: list[Path],
    ) -> None:
        """Test that hostname is included in generated D2D job file."""
        content = generate_content(default_test_files)

        assert 'HOSTNAME = "test-router-01"' in content

    def test_contains_environment_variable_setup(
        self,
        generate_content: Callable[[list[Path]], str],
        default_test_files: list[Path],
    ) -> None:
        """Test that DEVICE_INFO environment variable is set in D2D job file
        (required by SSHTestBase)."""
        content = generate_content(default_test_files)

        assert "os.environ['DEVICE_INFO'] = " in content
