# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Test base_test.py controller detection integration."""

import json
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pyats import aetest

from nac_test.pyats_core.common.base_test import NACTestBase


@pytest.fixture
def setup_test_data_file_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[Path, None, None]:
    """Create temp data file and set MERGED_DATA_MODEL_TEST_VARIABLES_FILEPATH."""
    temp_file = tmp_path / "test.yaml"
    temp_file.write_text("test: data")
    monkeypatch.setenv("MERGED_DATA_MODEL_TEST_VARIABLES_FILEPATH", str(temp_file))
    yield temp_file


class TestBaseTestControllerDetection:
    """Test controller detection integration in NACTestBase."""

    def test_base_test_detects_controller_on_setup(
        self, monkeypatch: pytest.MonkeyPatch, setup_test_data_file_env: Path
    ) -> None:
        """Test that NACTestBase detects controller type during setup."""
        monkeypatch.setenv("ACI_URL", "https://apic.example.com")
        monkeypatch.setenv("ACI_USERNAME", "admin")
        monkeypatch.setenv("ACI_PASSWORD", "password")

        class TestClass(NACTestBase):
            @aetest.test  # type: ignore[misc]
            def test_method(self) -> None:
                pass

        test_instance = TestClass()

        with patch.object(
            test_instance, "load_data_model", return_value={"test": "data"}
        ):
            test_instance.setup()

        assert test_instance.controller_type == "ACI"
        assert test_instance.controller_url == "https://apic.example.com"
        assert test_instance.username == "admin"
        assert test_instance.password == "password"

    def test_base_test_fails_setup_on_detection_error(
        self, monkeypatch: pytest.MonkeyPatch, setup_test_data_file_env: Path
    ) -> None:
        """Test that NACTestBase fails setup when controller detection fails."""
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

        class TestClass(NACTestBase):
            @aetest.test  # type: ignore[misc]
            def test_method(self) -> None:
                pass

        test_instance = TestClass()

        with patch.object(
            test_instance, "load_data_model", return_value={"test": "data"}
        ):
            with pytest.raises(ValueError) as exc_info:
                test_instance.setup()

            assert "No controller credentials found" in str(exc_info.value)

    def test_base_test_no_longer_uses_controller_type_env_var(
        self, monkeypatch: pytest.MonkeyPatch, setup_test_data_file_env: Path
    ) -> None:
        """Test that NACTestBase ignores CONTROLLER_TYPE environment variable."""
        monkeypatch.setenv("SDWAN_URL", "https://vmanage.example.com")
        monkeypatch.setenv("SDWAN_USERNAME", "admin")
        monkeypatch.setenv("SDWAN_PASSWORD", "password")
        monkeypatch.setenv("CONTROLLER_TYPE", "ACI")

        class TestClass(NACTestBase):
            @aetest.test  # type: ignore[misc]
            def test_method(self) -> None:
                pass

        test_instance = TestClass()

        with patch.object(
            test_instance, "load_data_model", return_value={"test": "data"}
        ):
            test_instance.setup()

        assert test_instance.controller_type == "SDWAN"
        assert test_instance.controller_url == "https://vmanage.example.com"

    def test_base_test_handles_multiple_controllers_error(
        self, monkeypatch: pytest.MonkeyPatch, setup_test_data_file_env: Path
    ) -> None:
        """Test that NACTestBase handles multiple controller credentials error during setup."""
        monkeypatch.setenv("ACI_URL", "https://apic.example.com")
        monkeypatch.setenv("ACI_USERNAME", "admin")
        monkeypatch.setenv("ACI_PASSWORD", "password")
        monkeypatch.setenv("CC_URL", "https://cc.example.com")
        monkeypatch.setenv("CC_USERNAME", "admin")
        monkeypatch.setenv("CC_PASSWORD", "password")

        class TestClass(NACTestBase):
            @aetest.test  # type: ignore[misc]
            def test_method(self) -> None:
                pass

        test_instance = TestClass()

        with patch.object(
            test_instance, "load_data_model", return_value={"test": "data"}
        ):
            with pytest.raises(ValueError) as exc_info:
                test_instance.setup()

            assert "Multiple controller credentials detected" in str(exc_info.value)


class TestBaseTestSetupErrorLogging:
    """Test that setup() logs errors via self.logger before re-raising."""

    def _make_test_instance(self) -> "NACTestBase":
        class TestClass(NACTestBase):
            @aetest.test  # type: ignore[misc]
            def test_method(self) -> None:
                pass

        return TestClass()

    @pytest.mark.parametrize(
        "exc,exc_type",
        [
            (ValueError("No controller credentials found"), ValueError),
            (KeyError("controller_type"), KeyError),
            (
                json.JSONDecodeError("Expecting value", "not-valid-json", 0),
                json.JSONDecodeError,
            ),
        ],
        ids=[
            "value_error",
            "key_error-missing_field",
            "json_decode_error-malformed_context",
        ],
    )
    def test_setup_logs_error_before_reraise(
        self,
        exc: Exception,
        exc_type: type[Exception],
        setup_test_data_file_env: Path,
    ) -> None:
        """setup() calls self.logger.error with 'Controller detection failed' before
        re-raising ValueError, KeyError, or JSONDecodeError from get_controller_context().
        """
        test_instance = self._make_test_instance()
        mock_logger = MagicMock()

        with (
            patch.object(
                test_instance, "load_data_model", return_value={"test": "data"}
            ),
            patch(
                "nac_test.pyats_core.common.base_test.get_controller_context",
                side_effect=exc,
            ),
            patch("logging.getLogger", return_value=mock_logger),
        ):
            with pytest.raises(exc_type):
                test_instance.setup()

        mock_logger.error.assert_called_once()
        assert "Controller detection failed" in mock_logger.error.call_args[0][0]
