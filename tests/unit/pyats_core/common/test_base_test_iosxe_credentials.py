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
        """setup() should fail for IOSXE without USERNAME/PASSWORD.

        IOSXE now requires IOSXE_USERNAME and IOSXE_PASSWORD in addition to
        IOSXE_URL (or IOSXE_HOST). Detection should report incomplete credentials.
        """
        # Remove USERNAME and PASSWORD to simulate incomplete IOSXE environment
        monkeypatch.delenv("IOSXE_USERNAME", raising=False)
        monkeypatch.delenv("IOSXE_PASSWORD", raising=False)

        # Verify environment is correct
        assert "IOSXE_URL" in os.environ
        assert "IOSXE_USERNAME" not in os.environ
        assert "IOSXE_PASSWORD" not in os.environ

        instance = nac_test_base_class.__new__(nac_test_base_class)

        # setup() should fail with incomplete credentials
        with pytest.raises(ValueError) as exc_info:
            instance.setup()

        error_msg = str(exc_info.value)
        assert "Incomplete controller credentials detected" in error_msg
        assert "IOSXE" in error_msg

    def test_iosxe_setup_works_with_username_password(
        self,
        nac_test_base_class: Any,
        temp_data_model_file: Path,
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
        temp_data_model_file: Path,
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
        temp_data_model_file: Path,
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
        assert "ACI: incomplete credentials" in str(exc_info.value)
