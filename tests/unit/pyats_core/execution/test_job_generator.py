# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for JobGenerator.

This module tests the JobGenerator class using a base class pattern for shared
tests between generate_job_file_content (API) and generate_device_centric_job (D2D).
"""

import ast
import logging
from collections.abc import Callable
from pathlib import Path

import pytest

from nac_test.pyats_core.execution.job_generator import JobGenerator
from nac_test.utils.logging import VerbosityLevel


class TestJobGeneratorInit:
    """Tests for JobGenerator initialization."""

    def test_pyats_managed_handlers_import(self) -> None:
        """Verify pyats.log.managed_handlers is importable and has screen attribute."""
        from pyats.log import managed_handlers

        assert hasattr(managed_handlers, "screen")
        assert hasattr(managed_handlers.screen, "setLevel")

    def test_init_default_verbosity(self, tmp_path: Path) -> None:
        """Test that default verbosity is WARNING."""
        generator = JobGenerator(max_workers=4, output_dir=tmp_path)

        assert generator.verbosity == VerbosityLevel.WARNING
        assert generator.loglevel == logging.WARNING

    @pytest.mark.parametrize(
        "verbosity,expected_loglevel",
        [
            (VerbosityLevel.DEBUG, logging.DEBUG),
            (VerbosityLevel.INFO, logging.INFO),
            (VerbosityLevel.WARNING, logging.WARNING),
            (VerbosityLevel.ERROR, logging.ERROR),
            (VerbosityLevel.CRITICAL, logging.CRITICAL),
        ],
    )
    def test_init_verbosity_to_loglevel_mapping(
        self, tmp_path: Path, verbosity: VerbosityLevel, expected_loglevel: int
    ) -> None:
        """Test that verbosity levels are correctly mapped to Python logging levels."""
        generator = JobGenerator(
            max_workers=4, output_dir=tmp_path, verbosity=verbosity
        )

        assert generator.verbosity == verbosity
        assert generator.loglevel == expected_loglevel


class BaseJobFileContentTests:
    """Base class with shared tests for both job file generation methods.

    Subclasses must define the `generate_content` fixture that returns a callable
    to generate job file content for the specific method being tested.
    """

    @pytest.fixture
    def generate_content(
        self, tmp_path: Path
    ) -> Callable[[VerbosityLevel | None, list[Path] | None], str]:
        """Return a callable that generates job file content.

        Must be overridden by subclasses.
        """
        raise NotImplementedError

    def test_generates_valid_python(
        self,
        generate_content: Callable[[VerbosityLevel | None, list[Path] | None], str],
    ) -> None:
        """Test that generated job file is syntactically valid Python."""
        content = generate_content(None, None)
        ast.parse(content)  # Raises SyntaxError if invalid

    def test_contains_managed_handlers_import(
        self,
        generate_content: Callable[[VerbosityLevel | None, list[Path] | None], str],
    ) -> None:
        """Test that generated job file imports managed_handlers at module level."""
        content = generate_content(None, None)
        assert "from pyats.log import managed_handlers" in content

    def test_contains_screen_handler_setlevel(
        self,
        generate_content: Callable[[VerbosityLevel | None, list[Path] | None], str],
    ) -> None:
        """Test that generated job file sets managed_handlers.screen.setLevel()."""
        content = generate_content(VerbosityLevel.WARNING, None)
        assert f"managed_handlers.screen.setLevel({logging.WARNING})" in content

    @pytest.mark.parametrize(
        "verbosity,expected_loglevel",
        [
            (VerbosityLevel.DEBUG, logging.DEBUG),
            (VerbosityLevel.INFO, logging.INFO),
            (VerbosityLevel.WARNING, logging.WARNING),
            (VerbosityLevel.ERROR, logging.ERROR),
            (VerbosityLevel.CRITICAL, logging.CRITICAL),
        ],
    )
    def test_verbosity_mapped_to_screen_handler(
        self,
        generate_content: Callable[[VerbosityLevel | None, list[Path] | None], str],
        verbosity: VerbosityLevel,
        expected_loglevel: int,
    ) -> None:
        """Test that verbosity level is correctly mapped in screen handler setLevel."""
        content = generate_content(verbosity, None)
        assert f"managed_handlers.screen.setLevel({expected_loglevel})" in content

    def test_converts_relative_paths_to_absolute(
        self,
        generate_content: Callable[[VerbosityLevel | None, list[Path] | None], str],
    ) -> None:
        """Test that relative test file paths are converted to absolute paths."""
        relative_paths = [Path("test1.py"), Path("subdir/test2.py")]

        content = generate_content(None, relative_paths)

        for rel_path in relative_paths:
            assert str(rel_path.resolve()) in content


class TestGenerateJobFileContent(BaseJobFileContentTests):
    """Tests for generate_job_file_content (API tests)."""

    @pytest.fixture
    def generate_content(
        self, tmp_path: Path
    ) -> Callable[[VerbosityLevel | None, list[Path] | None], str]:
        """Return callable that generates API job file content."""

        def _generate(
            verbosity: VerbosityLevel | None = None,
            test_files: list[Path] | None = None,
        ) -> str:
            generator = JobGenerator(
                max_workers=4,
                output_dir=tmp_path,
                verbosity=verbosity or VerbosityLevel.WARNING,
            )
            return generator.generate_job_file_content(
                test_files or [Path("/tmp/test1.py")]
            )

        return _generate

    def test_contains_max_workers(self, tmp_path: Path) -> None:
        """Test that max_workers is set in generated job file."""
        generator = JobGenerator(max_workers=8, output_dir=tmp_path)

        content = generator.generate_job_file_content([Path("/tmp/test1.py")])

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
    ) -> Callable[[VerbosityLevel | None, list[Path] | None], str]:
        """Return callable that generates D2D job file content."""

        def _generate(
            verbosity: VerbosityLevel | None = None,
            test_files: list[Path] | None = None,
        ) -> str:
            generator = JobGenerator(
                max_workers=4,
                output_dir=tmp_path,
                verbosity=verbosity or VerbosityLevel.WARNING,
            )
            return generator.generate_device_centric_job(
                sample_device, test_files or [Path("/tmp/d2d_test1.py")]
            )

        return _generate

    def test_contains_hostname(
        self, tmp_path: Path, sample_device: dict[str, str]
    ) -> None:
        """Test that hostname is included in generated D2D job file."""
        generator = JobGenerator(max_workers=4, output_dir=tmp_path)

        content = generator.generate_device_centric_job(
            sample_device, [Path("/tmp/d2d_test1.py")]
        )

        assert 'HOSTNAME = "test-router-01"' in content

    def test_contains_device_info_json(
        self, tmp_path: Path, sample_device: dict[str, str]
    ) -> None:
        """Test that device info is serialized as JSON in D2D job file."""
        generator = JobGenerator(max_workers=4, output_dir=tmp_path)

        content = generator.generate_device_centric_job(
            sample_device, [Path("/tmp/d2d_test1.py")]
        )

        assert "DEVICE_INFO = {" in content
        assert '"hostname": "test-router-01"' in content

    def test_contains_d2d_imports(
        self, tmp_path: Path, sample_device: dict[str, str]
    ) -> None:
        """Test that D2D-specific imports are present."""
        generator = JobGenerator(max_workers=4, output_dir=tmp_path)

        content = generator.generate_device_centric_job(
            sample_device, [Path("/tmp/d2d_test1.py")]
        )

        assert (
            "from nac_test.pyats_core.ssh.connection_manager import DeviceConnectionManager"
            in content
        )
        assert "from nac_test.utils import sanitize_hostname" in content

    def test_contains_environment_variable_setup(
        self, tmp_path: Path, sample_device: dict[str, str]
    ) -> None:
        """Test that DEVICE_INFO environment variable is set in D2D job file."""
        generator = JobGenerator(max_workers=4, output_dir=tmp_path)

        content = generator.generate_device_centric_job(
            sample_device, [Path("/tmp/d2d_test1.py")]
        )

        assert "os.environ['DEVICE_INFO'] = json.dumps(DEVICE_INFO)" in content
