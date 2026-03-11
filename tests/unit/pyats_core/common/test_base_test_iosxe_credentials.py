# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Tests for NACTestBase setup() with IOSXE controller (optional credentials).

IOSXE is unique among supported controllers - it's the only one that doesn't
require USERNAME/PASSWORD environment variables. This is because D2D tests
use device-specific credentials from the device inventory, not controller
credentials.

This test verifies that setup() handles optional credentials correctly for
IOSXE while still requiring them for other controller types.
"""

import os
import tempfile
from typing import Any

import pytest


@pytest.fixture()
def temp_data_model_file() -> Any:
    """Create temporary data model file for tests."""
    import json

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"defaults": {"iosxe": {}, "apic": {}}}, f)
        temp_file = f.name

    original = os.environ.get("MERGED_DATA_MODEL_TEST_VARIABLES_FILEPATH")
    os.environ["MERGED_DATA_MODEL_TEST_VARIABLES_FILEPATH"] = temp_file

    yield temp_file

    # Cleanup
    os.unlink(temp_file)
    if original:
        os.environ["MERGED_DATA_MODEL_TEST_VARIABLES_FILEPATH"] = original
    else:
        os.environ.pop("MERGED_DATA_MODEL_TEST_VARIABLES_FILEPATH", None)


class TestIOSXEOptionalCredentials:
    """Test that IOSXE controller type handles optional USERNAME/PASSWORD."""

    def test_iosxe_setup_works_without_username_password(
        self,
        nac_test_base_class: Any,
        temp_data_model_file: str,
        iosxe_controller_env: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """setup() should succeed for IOSXE with only URL (no USERNAME/PASSWORD).

        IOSXE is unique - it only requires IOSXE_URL per CONTROLLER_REGISTRY.
        D2D tests use device-specific credentials from inventory, not controller
        credentials.
        """
        # Remove USERNAME and PASSWORD to simulate real IOSXE environment
        monkeypatch.delenv("IOSXE_USERNAME", raising=False)
        monkeypatch.delenv("IOSXE_PASSWORD", raising=False)

        # Verify environment is correct
        assert "IOSXE_URL" in os.environ
        assert "IOSXE_USERNAME" not in os.environ
        assert "IOSXE_PASSWORD" not in os.environ

        # Create instance
        instance = nac_test_base_class.__new__(nac_test_base_class)

        # setup() should succeed even without USERNAME/PASSWORD
        instance.setup()

        assert instance.controller_type == "IOSXE"
        assert instance.controller_url == "https://test.example.com"
        assert instance.username is None
        assert instance.password is None

    def test_iosxe_setup_works_with_username_password(
        self,
        nac_test_base_class: Any,
        temp_data_model_file: str,
        iosxe_controller_env: None,
    ) -> None:
        """setup() should also work if IOSXE USERNAME/PASSWORD are provided.

        While not required, if someone sets them, we should accept them.
        """
        # Verify all credentials are set
        assert "IOSXE_URL" in os.environ
        assert "IOSXE_USERNAME" in os.environ
        assert "IOSXE_PASSWORD" in os.environ

        instance = nac_test_base_class.__new__(nac_test_base_class)
        instance.setup()

        assert instance.controller_type == "IOSXE"
        assert instance.controller_url == "https://test.example.com"
        assert instance.username == "test_user"
        assert instance.password == "test_pass"

    def test_aci_setup_requires_username_password(
        self,
        nac_test_base_class: Any,
        temp_data_model_file: str,
        aci_controller_env: None,
    ) -> None:
        """setup() should succeed for ACI with all required credentials.

        This verifies the normal 3-credential pattern still works for
        controller-based architectures like ACI.
        """
        # Verify all credentials are set
        assert "ACI_URL" in os.environ
        assert "ACI_USERNAME" in os.environ
        assert "ACI_PASSWORD" in os.environ

        instance = nac_test_base_class.__new__(nac_test_base_class)
        instance.setup()

        assert instance.controller_type == "ACI"
        assert instance.controller_url == "https://apic.test.com"
        assert instance.username == "admin"
        assert instance.password == "test_pass"

    def test_aci_setup_fails_without_username(
        self,
        nac_test_base_class: Any,
        temp_data_model_file: str,
        aci_controller_env: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Controller detection should fail for ACI without USERNAME.

        ACI requires all three credentials - detect_controller_type() should
        raise ValueError for incomplete credentials before setup() reads them.
        """
        monkeypatch.delenv("ACI_USERNAME", raising=False)

        instance = nac_test_base_class.__new__(nac_test_base_class)

        # setup() should fail during controller detection, not when reading env vars
        with pytest.raises(ValueError) as exc_info:
            instance.setup()

        assert "Incomplete controller credentials" in str(exc_info.value)
        assert "ACI: missing ACI_USERNAME" in str(exc_info.value)
