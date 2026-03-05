# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Shared fixtures for unit tests."""

import os
from pathlib import Path
from typing import Any, NamedTuple

import pytest
from _pytest.monkeypatch import MonkeyPatch

from nac_test.cli.validators.controller_auth import AuthCheckResult, AuthOutcome
from nac_test.pyats_core.constants import (
    PYATS_GRACEFUL_DISCONNECT_WAIT_SECONDS,
    PYATS_POST_DISCONNECT_WAIT_SECONDS,
)

CONTROLLER_ENV_PREFIXES = ("ACI_", "SDWAN_", "CC_", "MERAKI_", "FMC_", "ISE_")

AUTH_SUCCESS = AuthCheckResult(
    success=True,
    reason=AuthOutcome.SUCCESS,
    controller_type="ACI",
    controller_url="https://apic.test.com",
    detail="OK",
)

PYATS_TEST_FILE_CONTENT = """
from pyats import aetest
from nac_test_pyats_common.iosxe import IOSXETestBase
class Test(IOSXETestBase):
    @aetest.test
    def test(self):
        pass
"""

PYATS_D2D_TEST_FILE_CONTENT = PYATS_TEST_FILE_CONTENT

PYATS_API_TEST_FILE_CONTENT = """
from pyats import aetest
from nac_test_pyats_common.aci.test_base import APICTestBase
class Test(APICTestBase):
    @aetest.test
    def test(self):
        pass
"""

ROBOT_TEST_FILE_CONTENT = "*** Test Cases ***\nTest\n    Log    Hello"


def assert_connection_has_optimizations(connection: dict[str, Any]) -> None:
    """Verify connection includes expected optimization settings.

    This helper consolidates assertions for connection optimization settings,
    making it easier to maintain tests when new optimizations are added.

    Args:
        connection: The connection dict from testbed["devices"][hostname]["connections"]["cli"]
    """
    assert connection["arguments"]["init_config_commands"] == []
    assert connection["arguments"]["operating_mode"] is True
    assert (
        connection["settings"]["GRACEFUL_DISCONNECT_WAIT_SEC"]
        == PYATS_GRACEFUL_DISCONNECT_WAIT_SECONDS
    )
    assert (
        connection["settings"]["POST_DISCONNECT_WAIT_SEC"]
        == PYATS_POST_DISCONNECT_WAIT_SECONDS
    )


@pytest.fixture()
def clean_controller_env(monkeypatch: MonkeyPatch) -> None:
    """Clear all controller-related environment variables."""
    for key in list(os.environ.keys()):
        if any(prefix in key for prefix in CONTROLLER_ENV_PREFIXES):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture()
def aci_controller_env(monkeypatch: MonkeyPatch) -> None:
    """Set ACI controller environment variables."""
    monkeypatch.setenv("ACI_URL", "https://apic.test.com")
    monkeypatch.setenv("ACI_USERNAME", "admin")
    monkeypatch.setenv("ACI_PASSWORD", "password")


class PyATSTestEnv(NamedTuple):
    """Directory structure for PyATS orchestrator tests."""

    data_dir: Path
    test_dir: Path
    output_dir: Path
    merged_file: Path


@pytest.fixture()
def pyats_test_env(tmp_path: Path) -> PyATSTestEnv:
    """Create standard directory structure for PyATS orchestrator tests."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "test.yaml").write_text("test: data")
    test_dir = tmp_path / "tests"
    test_dir.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    merged_file = output_dir / "merged.yaml"
    merged_file.write_text("test: data")
    return PyATSTestEnv(
        data_dir=data_dir,
        test_dir=test_dir,
        output_dir=output_dir,
        merged_file=merged_file,
    )
