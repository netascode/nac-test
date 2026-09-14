# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Tests for NACTestBase setup() with IOSXE controller credentials.

IOSXE supports two URL forms (IOSXE_URL and IOSXE_HOST) via separate
credential sets, but always requires USERNAME and PASSWORD alongside
the URL/HOST variable. This test verifies that setup() handles IOSXE
credentials correctly.
"""

import json
import os
from pathlib import Path
from typing import Any

import pytest

from nac_test.core.controller import IncompleteCredentials, resolve_controller
from tests.conftest import resolve_and_inject_context


@pytest.fixture()
def temp_data_model_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Create temporary data model file for tests.

    Uses tmp_path for automatic cleanup and monkeypatch for env var management.
    """
    data_model_path = tmp_path / "data_model.json"
    data_model_path.write_text(json.dumps({"defaults": {"iosxe": {}, "apic": {}}}))
    monkeypatch.setenv(
        "MERGED_DATA_MODEL_TEST_VARIABLES_FILEPATH", str(data_model_path)
    )
    return data_model_path


class TestIOSXEOptionalCredentials:
    """Test that IOSXE controller type handles optional USERNAME/PASSWORD."""

    def test_iosxe_setup_fails_without_username_password(
        self,
        nac_test_base_class: Any,
        temp_data_model_file: Path,
        iosxe_controller_env: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """resolve_controller() should fail for IOSXE without USERNAME/PASSWORD.

        IOSXE requires IOSXE_USERNAME and IOSXE_PASSWORD in addition to
        IOSXE_URL (or IOSXE_HOST). Resolution reports incomplete credentials.
        """
        # Remove USERNAME and PASSWORD to simulate incomplete IOSXE environment
        monkeypatch.delenv("IOSXE_USERNAME", raising=False)
        monkeypatch.delenv("IOSXE_PASSWORD", raising=False)

        # Verify environment is correct
        assert "IOSXE_URL" in os.environ
        assert "IOSXE_USERNAME" not in os.environ
        assert "IOSXE_PASSWORD" not in os.environ

        with pytest.raises(IncompleteCredentials) as exc_info:
            resolve_controller()

        assert "IOSXE" in exc_info.value.partial_controllers

    def test_iosxe_setup_works_with_username_password(
        self,
        nac_test_base_class: Any,
        temp_data_model_file: Path,
        iosxe_controller_env: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """setup() works when IOSXE credentials and context are provided."""
        # Verify all credentials are set
        assert "IOSXE_URL" in os.environ
        assert "IOSXE_USERNAME" in os.environ
        assert "IOSXE_PASSWORD" in os.environ

        resolve_and_inject_context(monkeypatch)

        instance = nac_test_base_class.__new__(nac_test_base_class)
        instance.setup()

        assert instance.controller_type == "IOSXE"
        assert instance.controller_url == "https://test.example.com"
        assert instance.username == "test_user"
        assert instance.password == "test_pass"

    def test_aci_setup_requires_username_password(
        self,
        nac_test_base_class: Any,
        temp_data_model_file: Path,
        aci_controller_env: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """setup() should succeed for ACI with all required credentials.

        This verifies the normal 3-credential pattern still works for
        controller-based architectures like ACI.
        """
        # Verify all credentials are set
        assert "ACI_URL" in os.environ
        assert "ACI_USERNAME" in os.environ
        assert "ACI_PASSWORD" in os.environ

        resolve_and_inject_context(monkeypatch)

        instance = nac_test_base_class.__new__(nac_test_base_class)
        instance.setup()

        assert instance.controller_type == "ACI"
        assert instance.controller_url == "https://apic.test.com"
        assert instance.username == "admin"
        assert instance.password == "test_pass"

    def test_aci_setup_fails_without_username(
        self,
        nac_test_base_class: Any,
        temp_data_model_file: Path,
        aci_controller_env: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Controller resolution should fail for ACI without USERNAME.

        ACI requires all three credentials - resolve_controller() should
        raise IncompleteCredentials.
        """
        monkeypatch.delenv("ACI_USERNAME", raising=False)

        with pytest.raises(IncompleteCredentials) as exc_info:
            resolve_controller()

        assert "ACI" in exc_info.value.partial_controllers
