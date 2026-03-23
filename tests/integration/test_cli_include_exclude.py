# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Integration tests for --include/--exclude tag filtering.

Only the "no tests matched" scenario (exit 252) is tested here as a real
Robot Framework execution. The wiring of include/exclude tags through the
CLI → RobotOrchestrator → run_pabot call is covered by the unit test
test_include_exclude_tags_passed_to_pabot in tests/unit/robot/test_orchestrator.py.
Testing exit codes for specific failure counts (e.g. --include smoke → 3 failures)
would exercise Robot Framework's own filtering logic rather than nac-test's wiring,
which is not our responsibility to test.
"""

from pathlib import Path

import pytest
from typer.testing import CliRunner

import nac_test.cli.main
from nac_test.core.constants import EXIT_DATA_ERROR

pytestmark = [
    pytest.mark.integration,
]


def test_include_nonexistent_tag_returns_252(tmp_path: Path) -> None:
    """Test that --include with a tag matching no tests produces exit code 252.

    This is the only scenario tested end-to-end: it verifies that Robot
    Framework's "no tests found" exit code (EXIT_DATA_ERROR) is correctly
    propagated through pabot → RobotOrchestrator → CombinedResults → CLI.

    Args:
        tmp_path: Pytest fixture providing a temporary directory.
    """
    runner = CliRunner()
    result = runner.invoke(
        nac_test.cli.main.app,
        [
            "-d",
            "tests/integration/fixtures/data/",
            "-t",
            "tests/integration/fixtures/templates_extra_args/",
            "-o",
            str(tmp_path),
            "--include",
            "DoesNotExist",
        ],
    )
    assert result.exit_code == EXIT_DATA_ERROR, (
        f"--include with non-matching tag should produce exit {EXIT_DATA_ERROR}, "
        f"got {result.exit_code}:\n{result.output}"
    )
