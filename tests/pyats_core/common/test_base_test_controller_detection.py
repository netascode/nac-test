# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Test base_test.py controller detection integration."""

from pathlib import Path
from unittest.mock import patch

import pytest
from pyats import aetest

from nac_test.pyats_core.common.base_test import NACTestBase


class TestBaseTestControllerDetection:
    """Test controller detection integration in NACTestBase."""

    def test_base_test_detects_controller_on_setup(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that NACTestBase detects controller type during setup."""
        # Set up ACI environment variables
        monkeypatch.setenv("ACI_URL", "https://apic.example.com")
        monkeypatch.setenv("ACI_USERNAME", "admin")
        monkeypatch.setenv("ACI_PASSWORD", "password")

        # Create actual temp file to avoid artifacts in cwd
        temp_file = tmp_path / "test.yaml"
        temp_file.write_text("test: data")
        monkeypatch.setenv("MERGED_DATA_MODEL_TEST_VARIABLES_FILEPATH", str(temp_file))

        # Create a mock test class
        class TestClass(NACTestBase):
            @aetest.test  # type: ignore[untyped-decorator]
            def test_method(self) -> None:
                pass

        # Create instance and run setup
        test_instance = TestClass()

        # Mock the load_data_model method to avoid file I/O
        with patch.object(
            test_instance, "load_data_model", return_value={"test": "data"}
        ):
            test_instance.setup()

        # Verify controller type was detected
        assert test_instance.controller_type == "ACI"
        assert test_instance.controller_url == "https://apic.example.com"
        assert test_instance.username == "admin"
        assert test_instance.password == "password"

    def test_base_test_fails_setup_on_detection_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that NACTestBase fails setup when controller detection fails."""
        # Clear all controller environment variables
        for env_var in [
            "ACI_URL",
            "ACI_USERNAME",
            "ACI_PASSWORD",
            "SDWAN_URL",
            "SDWAN_USERNAME",
            "SDWAN_PASSWORD",
            "CC_URL",
            "CC_USERNAME",
            "CC_PASSWORD",
        ]:
            monkeypatch.delenv(env_var, raising=False)

        # Create actual temp file to avoid artifacts in cwd
        temp_file = tmp_path / "test.yaml"
        temp_file.write_text("test: data")
        monkeypatch.setenv("MERGED_DATA_MODEL_TEST_VARIABLES_FILEPATH", str(temp_file))

        # Create a mock test class
        class TestClass(NACTestBase):
            @aetest.test  # type: ignore[untyped-decorator]
            def test_method(self) -> None:
                pass

        # Create instance
        test_instance = TestClass()

        # Mock the load_data_model method to avoid file I/O
        with patch.object(
            test_instance, "load_data_model", return_value={"test": "data"}
        ):
            # Setup should raise ValueError due to missing credentials
            with pytest.raises(ValueError) as exc_info:
                test_instance.setup()

            # Verify the error message is about missing credentials
            assert "No controller credentials found" in str(exc_info.value)

    def test_base_test_no_longer_uses_controller_type_env_var(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that NACTestBase ignores CONTROLLER_TYPE environment variable."""
        # Set up SDWAN credentials
        monkeypatch.setenv("SDWAN_URL", "https://vmanage.example.com")
        monkeypatch.setenv("SDWAN_USERNAME", "admin")
        monkeypatch.setenv("SDWAN_PASSWORD", "password")

        # Also set CONTROLLER_TYPE to a different value (should be ignored)
        monkeypatch.setenv("CONTROLLER_TYPE", "ACI")

        # Create actual temp file to avoid artifacts in cwd
        temp_file = tmp_path / "test.yaml"
        temp_file.write_text("test: data")
        monkeypatch.setenv("MERGED_DATA_MODEL_TEST_VARIABLES_FILEPATH", str(temp_file))

        # Create a mock test class
        class TestClass(NACTestBase):
            @aetest.test  # type: ignore[untyped-decorator]
            def test_method(self) -> None:
                pass

        # Create instance and run setup
        test_instance = TestClass()

        # Mock the load_data_model method to avoid file I/O
        with patch.object(
            test_instance, "load_data_model", return_value={"test": "data"}
        ):
            test_instance.setup()

        # Verify controller type was detected based on credentials (SDWAN), not CONTROLLER_TYPE env var
        assert test_instance.controller_type == "SDWAN"
        assert test_instance.controller_url == "https://vmanage.example.com"

    def test_base_test_handles_multiple_controllers_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test that NACTestBase handles multiple controller credentials error during setup."""
        # Set up both ACI and CC environment variables
        monkeypatch.setenv("ACI_URL", "https://apic.example.com")
        monkeypatch.setenv("ACI_USERNAME", "admin")
        monkeypatch.setenv("ACI_PASSWORD", "password")
        monkeypatch.setenv("CC_URL", "https://cc.example.com")
        monkeypatch.setenv("CC_USERNAME", "admin")
        monkeypatch.setenv("CC_PASSWORD", "password")

        # Create actual temp file to avoid artifacts in cwd
        temp_file = tmp_path / "test.yaml"
        temp_file.write_text("test: data")
        monkeypatch.setenv("MERGED_DATA_MODEL_TEST_VARIABLES_FILEPATH", str(temp_file))

        # Create a mock test class
        class TestClass(NACTestBase):
            @aetest.test  # type: ignore[untyped-decorator]
            def test_method(self) -> None:
                pass

        # Create instance
        test_instance = TestClass()

        # Mock the load_data_model method to avoid file I/O
        with patch.object(
            test_instance, "load_data_model", return_value={"test": "data"}
        ):
            # Setup should raise ValueError due to multiple controller credentials
            with pytest.raises(ValueError) as exc_info:
                test_instance.setup()

            # Verify the error message is about multiple controllers
            assert "Multiple controller credentials detected" in str(exc_info.value)
