# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Integration tests for CleanupManager atexit and signal behaviour.

Spawns isolated subprocesses so that atexit fires in a real interpreter
exit, not a mock or in-process call, and so that signals are actually
delivered to the process rather than simulated via direct method calls.
"""

import os
import signal
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

_ATEXIT_SCRIPT = """
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

_SIGNAL_SCRIPT = """
import sys
import time
from pathlib import Path
from nac_test.utils.cleanup import get_cleanup_manager

get_cleanup_manager().register(Path("{sentinel}"))

sys.stdout.write("ready\\n")
sys.stdout.flush()

time.sleep(30)
"""


@pytest.mark.windows
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
        [sys.executable, "-c", _ATEXIT_SCRIPT.format(sentinel=str(sentinel))],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert sentinel.exists() is expect_exists


@pytest.mark.parametrize(
    "signum",
    [signal.SIGTERM, signal.SIGINT],
    ids=["SIGTERM", "SIGINT"],
)
def test_cleanup_on_signal(tmp_path: Path, signum: signal.Signals) -> None:
    """CleanupManager deletes registered files when the process receives SIGTERM or SIGINT.

    Delivers an actual signal to a child process (not a direct _signal_handler()
    call) so that the signal registration path in _install_signal_handlers() is
    exercised end-to-end. SIGTERM and SIGINT have distinct re-raise paths:
    SIGTERM re-sends the signal via signal.raise_signal(); SIGINT raises
    KeyboardInterrupt. Both must still delete registered files before exiting.
    """
    sentinel = tmp_path / "sensitive.yaml"
    sentinel.write_text("secret: value")

    proc = subprocess.Popen(
        [sys.executable, "-c", _SIGNAL_SCRIPT.format(sentinel=str(sentinel))],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Wait until the child signals it is ready (handlers installed, file registered).
    try:
        ready_line = proc.stdout.readline()  # type: ignore[union-attr]
        assert ready_line.strip() == "ready", f"Unexpected output: {ready_line!r}"
    except Exception as e:
        proc.kill()
        proc.wait()
        raise AssertionError(f"Child process failed to signal readiness: {e}") from e

    proc.send_signal(signum)

    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired as e:
        proc.kill()
        proc.wait()
        raise AssertionError(
            f"Child process did not exit within 10 s after {signum.name}"
        ) from e

    assert not sentinel.exists(), (
        f"{sentinel.name} was not deleted after {signum.name} — "
        "CleanupManager signal handler may not be registered correctly"
    )
