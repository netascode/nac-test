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
        """setup() raises when the context is valid but IOSXE credentials are gone.

        IOSXE requires IOSXE_USERNAME and IOSXE_PASSWORD in addition to
        IOSXE_URL (or IOSXE_HOST). The orchestrator resolved the controller,
        so a failure in get_connection_params() is a real misconfiguration.
        """
        resolve_and_inject_context(monkeypatch)
        monkeypatch.delenv("IOSXE_USERNAME")
        monkeypatch.delenv("IOSXE_PASSWORD")

        instance = nac_test_base_class.__new__(nac_test_base_class)
        with pytest.raises(ValueError, match="IOSXE_USERNAME"):
            instance.setup()

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
        """setup() raises when the context is valid but ACI_USERNAME is gone."""
        resolve_and_inject_context(monkeypatch)
        monkeypatch.delenv("ACI_USERNAME")

        instance = nac_test_base_class.__new__(nac_test_base_class)
        with pytest.raises(ValueError, match="ACI_USERNAME"):
            instance.setup()
