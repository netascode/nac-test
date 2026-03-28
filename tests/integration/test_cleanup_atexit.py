# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Integration tests for CleanupManager atexit behaviour.

Spawns isolated subprocesses so that atexit fires in a real interpreter
exit, not a mock or in-process call.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.windows,
]

_SCRIPT = """
import os
import typer
from pathlib import Path
from nac_test.utils.cleanup import get_cleanup_manager

app = typer.Typer()

@app.command()
def main() -> None:
    get_cleanup_manager().register(Path("{sentinel}"), keep_if_debug=True)
    raise typer.Exit(0)

app()
"""


@pytest.mark.parametrize(
    ("debug_env", "expect_exists"),
    [
        (None, False),  # NAC_TEST_DEBUG unset  → file is deleted
        ("true", True),  # NAC_TEST_DEBUG=true   → file is kept
    ],
)
def test_cleanup_atexit_via_typer_exit(
    tmp_path: Path, debug_env: str | None, expect_exists: bool
) -> None:
    """CleanupManager deletes (or retains) registered files on typer.Exit(0).

    Exercises the exact production exit path and the keep_if_debug flag.
    """
    sentinel = tmp_path / "job.py"
    sentinel.write_text("# temp job")

    env = None
    if debug_env is not None:
        env = os.environ.copy()
        env["NAC_TEST_DEBUG"] = debug_env

    result = subprocess.run(
        [sys.executable, "-c", _SCRIPT.format(sentinel=str(sentinel))],
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert sentinel.exists() is expect_exists
