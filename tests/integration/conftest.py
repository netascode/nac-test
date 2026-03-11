# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Shared fixtures for integration tests."""

import shutil
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from nac_test.cli.validators.controller_auth import AuthCheckResult, AuthOutcome


@pytest.fixture
def temp_cwd_dir() -> Generator[str, None, None]:
    """Create a temporary directory under the current working directory.

    Integration tests use this fixture to exercise relative output handling
    from the repo root instead of an absolute system temp path.

    Yields:
        str: Relative path string to the created directory.
    """
    cwd = Path.cwd()
    temp_dir = Path(tempfile.mkdtemp(dir=cwd, prefix="__nac_tmp_"))
    try:
        yield str(temp_dir.relative_to(cwd))
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def setup_bogus_controller_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set up environment variables for a bogus ACI controller.

    Uses monkeypatch for safe, automatic cleanup that preserves
    original environment state even if tests fail.

    Also mocks the preflight auth check and controller detection so that
    Robot rendering/execution integration tests are not blocked by
    unreachable controller credentials.

    Args:
        monkeypatch: Pytest monkeypatch fixture for safe environment manipulation.
    """
    monkeypatch.setenv("ACI_URL", "foo")
    monkeypatch.setenv("ACI_USERNAME", "foo")
    monkeypatch.setenv("ACI_PASSWORD", "foo")

    # Bypass preflight auth check — integration tests validate Robot behavior,
    # not controller authentication.
    monkeypatch.setattr(
        "nac_test.combined_orchestrator.detect_controller_type", lambda: "ACI"
    )
    monkeypatch.setattr(
        "nac_test.combined_orchestrator.preflight_auth_check",
        lambda _: AuthCheckResult(
            success=True,
            reason=AuthOutcome.SUCCESS,
            controller_type="ACI",
            controller_url="foo",
            detail="OK",
        ),
    )
