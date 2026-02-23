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
from typing import Any
from unittest.mock import patch

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

    def test_temp_files_cleaned_up_on_success(self, tmp_path: Path) -> None:
        """Test that temp files are cleaned up after successful execution."""
        # Redirect temp files to isolated directory to avoid race conditions
        # with parallel tests (see issue #568)
        original = tempfile.NamedTemporaryFile

        def patched_named_temp_file(*args: Any, **kwargs: Any) -> Any:
            kwargs.setdefault("dir", str(tmp_path))
            return original(*args, **kwargs)

        with patch.object(tempfile, "NamedTemporaryFile", patched_named_temp_file):
            execute_auth_subprocess({"key": "value"}, 'result = {"success": True}')

        assert list(tmp_path.glob("*_auth_*.json")) == []
        assert list(tmp_path.glob("*_auth_script.py")) == []

    def test_temp_files_cleaned_up_on_error(self, tmp_path: Path) -> None:
        """Test that temp files are cleaned up even when script errors."""
        # Redirect temp files to isolated directory to avoid race conditions
        # with parallel tests (see issue #568)
        original = tempfile.NamedTemporaryFile

        def patched_named_temp_file(*args: Any, **kwargs: Any) -> Any:
            kwargs.setdefault("dir", str(tmp_path))
            return original(*args, **kwargs)

        with patch.object(tempfile, "NamedTemporaryFile", patched_named_temp_file):
            with pytest.raises(SubprocessAuthError):
                execute_auth_subprocess({}, 'raise Exception("Intentional error")')

        assert list(tmp_path.glob("*_auth_*.json")) == []

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
