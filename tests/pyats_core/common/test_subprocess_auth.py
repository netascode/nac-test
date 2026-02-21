# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Unit tests for subprocess_auth module.

Tests the fork-safe subprocess authentication mechanism:
1. Secure file permissions setting
2. Auth subprocess execution and result handling
3. Error propagation and cleanup
"""

import os
import tempfile
from pathlib import Path

import pytest

from nac_test.pyats_core.common.subprocess_auth import (
    SubprocessAuthError,
    _set_secure_permissions,
    execute_auth_subprocess,
)


class TestSetSecurePermissions:
    """Test secure file permissions."""

    def test_sets_permissions_on_file(self) -> None:
        """Test that secure permissions are set on a file."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name

        try:
            _set_secure_permissions(path)
            if os.name != "nt":
                # On Unix, check permissions are 0600
                mode = os.stat(path).st_mode & 0o777
                assert mode == 0o600
        finally:
            os.unlink(path)


class TestExecuteAuthSubprocess:
    """Test the main subprocess execution function."""

    def test_successful_execution(self) -> None:
        """Test successful auth subprocess execution."""
        auth_params = {"key": "value", "number": 42}
        auth_script = (
            'result = {"token": "test-token-123", "received_key": params["key"]}'
        )

        result = execute_auth_subprocess(auth_params, auth_script)

        assert result["token"] == "test-token-123"
        assert result["received_key"] == "value"

    def test_params_available_in_script(self) -> None:
        """Test that auth_params are available as 'params' in the script."""
        auth_params = {
            "url": "https://example.com",
            "username": "admin",
            "password": "secret",
        }
        auth_script = """
result = {
    "url_received": params["url"],
    "user_received": params["username"],
    "pass_length": len(params["password"])
}
"""
        result = execute_auth_subprocess(auth_params, auth_script)

        assert result["url_received"] == "https://example.com"
        assert result["user_received"] == "admin"
        assert result["pass_length"] == 6

    def test_script_error_raises_exception(self) -> None:
        """Test that script errors are captured and raised as SubprocessAuthError."""
        auth_params: dict[str, str] = {}
        auth_script = 'raise ValueError("Test error message")'

        with pytest.raises(SubprocessAuthError) as exc_info:
            execute_auth_subprocess(auth_params, auth_script)

        assert "Test error message" in str(exc_info.value)

    def test_error_in_result_raises_exception(self) -> None:
        """Test that error key in result raises SubprocessAuthError."""
        auth_params: dict[str, str] = {}
        auth_script = 'result = {"error": "Authentication failed: invalid credentials"}'

        with pytest.raises(SubprocessAuthError) as exc_info:
            execute_auth_subprocess(auth_params, auth_script)

        assert "invalid credentials" in str(exc_info.value)

    def test_missing_result_raises_exception(self) -> None:
        """Test that not setting result raises SubprocessAuthError."""
        auth_params: dict[str, str] = {}
        auth_script = "x = 1 + 1  # Does not set result"

        with pytest.raises(SubprocessAuthError) as exc_info:
            execute_auth_subprocess(auth_params, auth_script)

        assert "did not set result" in str(exc_info.value)

    def test_temp_files_cleaned_up_on_success(self) -> None:
        """Test that temp files are cleaned up after successful execution."""
        auth_params = {"key": "value"}
        auth_script = 'result = {"success": True}'

        # Get temp directory
        temp_dir = tempfile.gettempdir()

        # Count auth-related files before
        auth_files_before = len(list(Path(temp_dir).glob("*_auth_*.json")))
        script_files_before = len(list(Path(temp_dir).glob("*_auth_script.py")))

        execute_auth_subprocess(auth_params, auth_script)

        # Count auth-related files after
        auth_files_after = len(list(Path(temp_dir).glob("*_auth_*.json")))
        script_files_after = len(list(Path(temp_dir).glob("*_auth_script.py")))

        # Should be same count (files were cleaned up)
        assert auth_files_after == auth_files_before
        assert script_files_after == script_files_before

    def test_temp_files_cleaned_up_on_error(self) -> None:
        """Test that temp files are cleaned up even when script errors."""
        auth_params: dict[str, str] = {}
        auth_script = 'raise Exception("Intentional error")'

        temp_dir = tempfile.gettempdir()
        auth_files_before = len(list(Path(temp_dir).glob("*_auth_*.json")))

        with pytest.raises(SubprocessAuthError):
            execute_auth_subprocess(auth_params, auth_script)

        auth_files_after = len(list(Path(temp_dir).glob("*_auth_*.json")))
        assert auth_files_after == auth_files_before

    def test_complex_auth_params(self) -> None:
        """Test with complex nested auth params."""
        auth_params = {
            "url": "https://api.example.com",
            "credentials": {"user": "admin", "pass": "secret"},
            "options": {"timeout": 30, "verify_ssl": False},
            "tags": ["prod", "api"],
        }
        auth_script = """
result = {
    "url": params["url"],
    "user": params["credentials"]["user"],
    "timeout": params["options"]["timeout"],
    "tag_count": len(params["tags"])
}
"""
        result = execute_auth_subprocess(auth_params, auth_script)

        assert result["url"] == "https://api.example.com"
        assert result["user"] == "admin"
        assert result["timeout"] == 30
        assert result["tag_count"] == 2


class TestSubprocessAuthError:
    """Test the SubprocessAuthError exception class."""

    def test_is_runtime_error(self) -> None:
        """Test that SubprocessAuthError is a RuntimeError."""
        assert issubclass(SubprocessAuthError, RuntimeError)

    def test_can_be_raised_with_message(self) -> None:
        """Test that SubprocessAuthError can be raised with a message."""
        with pytest.raises(SubprocessAuthError, match="Test authentication failure"):
            raise SubprocessAuthError("Test authentication failure")

    def test_can_be_caught_as_runtime_error(self) -> None:
        """Test that SubprocessAuthError can be caught as RuntimeError."""
        try:
            raise SubprocessAuthError("Test")
        except RuntimeError as e:
            assert "Test" in str(e)
