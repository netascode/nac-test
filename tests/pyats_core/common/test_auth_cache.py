# -*- coding: utf-8 -*-

"""Unit tests for nac_test.pyats_core.common.auth_cache module.

This module tests the AuthCache class which provides generic file-based
authentication caching for parallel processes. The tests cover:
- Cache hit scenarios (valid cached data exists)
- Cache miss scenarios (no cached data)
- Cache expiry scenarios (TTL exceeded)
- File locking behavior for concurrent access
- Both modes of _cache_auth_data (extract_token True/False)
- Backward compatibility of get_or_create_token
"""

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Tuple
from unittest.mock import Mock

import pytest

from nac_test.pyats_core.common.auth_cache import AuthCache

if TYPE_CHECKING:
    from pytest_mock.plugin import MockerFixture


@pytest.fixture
def mock_time(mocker: "MockerFixture") -> Any:
    """Fixture to mock time.time() for testing TTL behavior.

    Args:
        mocker: Pytest mocker fixture for creating mocks.

    Returns:
        Mock object for time.time that can be configured per test.
    """
    return mocker.patch(
        "nac_test.pyats_core.common.auth_cache.time.time", return_value=1000.0
    )


@pytest.fixture
def mock_auth_cache_dir(mocker: "MockerFixture", tmp_path: Path) -> Path:
    """Fixture to provide a temporary auth cache directory.

    Args:
        mocker: Pytest mocker fixture for creating mocks.
        tmp_path: Pytest fixture providing a temporary directory.

    Returns:
        Path to temporary auth cache directory for testing.
    """
    cache_dir = tmp_path / "auth-cache"
    cache_dir.mkdir(exist_ok=True)
    mocker.patch("nac_test.pyats_core.common.auth_cache.AUTH_CACHE_DIR", str(cache_dir))
    return cache_dir


@pytest.fixture
def mock_fcntl(mocker: "MockerFixture") -> Any:
    """Fixture to mock file locking operations.

    Args:
        mocker: Pytest mocker fixture for creating mocks.

    Returns:
        Mock object for fcntl.flock operations.
    """
    return mocker.patch("fcntl.flock")


@pytest.fixture
def sample_auth_func() -> Mock:
    """Fixture providing a mock authentication function.

    Returns:
        Mock callable that returns (auth_data, expires_in_seconds).
    """
    mock_func = Mock(return_value=("test-token-123", 3600))
    return mock_func


@pytest.fixture
def sample_dict_auth_func() -> Mock:
    """Fixture providing a mock authentication function that returns a dict.

    Returns:
        Mock callable that returns (auth_dict, expires_in_seconds).
    """
    auth_data = {
        "token": "dict-token-456",
        "refresh_token": "refresh-789",
        "user_id": "user123",
    }
    mock_func = Mock(return_value=(auth_data, 7200))
    return mock_func


class TestAuthCacheInternal:
    """Test cases for the internal _cache_auth_data method."""

    def test_cache_miss_token_mode(
        self,
        mock_auth_cache_dir: Path,
        mock_fcntl: Mock,
        mock_time: Mock,
        sample_auth_func: Mock,
    ) -> None:
        """Test _cache_auth_data when no cached data exists (token mode).

        This test verifies that when there's no existing cache file,
        the auth function is called and the token is properly cached
        and returned in extract_token=True mode.

        Args:
            mock_auth_cache_dir: Mocked auth cache directory path.
            mock_fcntl: Mocked file locking.
            mock_time: Mocked time.time() for consistent testing.
            sample_auth_func: Mock authentication function.
        """
        # Arrange
        controller_type = "APIC"
        url = "https://controller.example.com"

        # Act
        result = AuthCache._cache_auth_data(
            controller_type=controller_type,
            url=url,
            auth_func=sample_auth_func,
            extract_token=True,
        )

        # Assert
        assert result == "test-token-123"
        sample_auth_func.assert_called_once()

        # Verify cache file was created with correct content
        cache_files = list(mock_auth_cache_dir.glob("*.json"))
        assert len(cache_files) == 1

        with open(cache_files[0], "r") as f:
            cached_data = json.load(f)
            assert cached_data["token"] == "test-token-123"
            assert (
                cached_data["expires_at"] == 1000.0 + 3600 - 60
            )  # current_time + expires_in - buffer

    def test_cache_miss_dict_mode(
        self,
        mock_auth_cache_dir: Path,
        mock_fcntl: Mock,
        mock_time: Mock,
        sample_dict_auth_func: Mock,
    ) -> None:
        """Test _cache_auth_data when no cached data exists (dict mode).

        This test verifies that when there's no existing cache file,
        the auth function is called and the dict is properly cached
        and returned in extract_token=False mode.

        Args:
            mock_auth_cache_dir: Mocked auth cache directory path.
            mock_fcntl: Mocked file locking.
            mock_time: Mocked time.time() for consistent testing.
            sample_dict_auth_func: Mock authentication function returning dict.
        """
        # Arrange
        controller_type = "CC"
        url = "https://cc.example.com"

        # Act
        result = AuthCache._cache_auth_data(
            controller_type=controller_type,
            url=url,
            auth_func=sample_dict_auth_func,
            extract_token=False,
        )

        # Assert
        expected_result = {
            "token": "dict-token-456",
            "refresh_token": "refresh-789",
            "user_id": "user123",
        }
        assert result == expected_result
        sample_dict_auth_func.assert_called_once()

        # Verify cache file was created with correct content
        cache_files = list(mock_auth_cache_dir.glob("*.json"))
        assert len(cache_files) == 1

        with open(cache_files[0], "r") as f:
            cached_data = json.load(f)
            assert cached_data["token"] == "dict-token-456"
            assert cached_data["refresh_token"] == "refresh-789"
            assert cached_data["user_id"] == "user123"
            assert cached_data["expires_at"] == 1000.0 + 7200 - 60

    def test_cache_hit_token_mode(
        self,
        mock_auth_cache_dir: Path,
        mock_fcntl: Mock,
        mock_time: Mock,
        sample_auth_func: Mock,
    ) -> None:
        """Test _cache_auth_data when valid cached data exists (token mode).

        This test verifies that when a valid cache file exists (not expired),
        the cached token is returned without calling the auth function
        in extract_token=True mode.

        Args:
            mock_auth_cache_dir: Mocked auth cache directory path.
            mock_fcntl: Mocked file locking.
            mock_time: Mocked time.time() for consistent testing.
            sample_auth_func: Mock authentication function.
        """
        # Arrange
        controller_type = "APIC"
        url = "https://controller.example.com"

        # Pre-create a valid cache file
        import hashlib

        url_hash = hashlib.md5(url.encode()).hexdigest()
        cache_file = mock_auth_cache_dir / f"APIC_{url_hash}.json"
        cache_data = {
            "token": "cached-token-999",
            "expires_at": 2000.0,  # Future time (current mock time is 1000.0)
        }
        with open(cache_file, "w") as f:
            json.dump(cache_data, f)

        # Act
        result = AuthCache._cache_auth_data(
            controller_type=controller_type,
            url=url,
            auth_func=sample_auth_func,
            extract_token=True,
        )

        # Assert
        assert result == "cached-token-999"
        sample_auth_func.assert_not_called()  # Should not call auth function

    def test_cache_hit_dict_mode(
        self,
        mock_auth_cache_dir: Path,
        mock_fcntl: Mock,
        mock_time: Mock,
        sample_dict_auth_func: Mock,
    ) -> None:
        """Test _cache_auth_data when valid cached data exists (dict mode).

        This test verifies that when a valid cache file exists (not expired),
        the cached dict is returned without calling the auth function
        in extract_token=False mode, with expires_at removed.

        Args:
            mock_auth_cache_dir: Mocked auth cache directory path.
            mock_fcntl: Mocked file locking.
            mock_time: Mocked time.time() for consistent testing.
            sample_dict_auth_func: Mock authentication function returning dict.
        """
        # Arrange
        controller_type = "CC"
        url = "https://cc.example.com"

        # Pre-create a valid cache file with dict data
        import hashlib

        url_hash = hashlib.md5(url.encode()).hexdigest()
        cache_file = mock_auth_cache_dir / f"CC_{url_hash}.json"
        cache_data = {
            "token": "cached-dict-token",
            "refresh_token": "cached-refresh",
            "user_id": "cached-user",
            "expires_at": 2000.0,  # Future time
        }
        with open(cache_file, "w") as f:
            json.dump(cache_data, f)

        # Act
        result = AuthCache._cache_auth_data(
            controller_type=controller_type,
            url=url,
            auth_func=sample_dict_auth_func,
            extract_token=False,
        )

        # Assert
        expected_result = {
            "token": "cached-dict-token",
            "refresh_token": "cached-refresh",
            "user_id": "cached-user",
        }
        assert result == expected_result  # expires_at should be removed
        sample_dict_auth_func.assert_not_called()

    def test_cache_expired_token_mode(
        self,
        mock_auth_cache_dir: Path,
        mock_fcntl: Mock,
        mock_time: Mock,
        sample_auth_func: Mock,
    ) -> None:
        """Test _cache_auth_data when cached data is expired (token mode).

        This test verifies that when a cache file exists but is expired,
        the auth function is called to get a new token and the cache
        is updated in extract_token=True mode.

        Args:
            mock_auth_cache_dir: Mocked auth cache directory path.
            mock_fcntl: Mocked file locking.
            mock_time: Mocked time.time() for consistent testing.
            sample_auth_func: Mock authentication function.
        """
        # Arrange
        controller_type = "APIC"
        url = "https://controller.example.com"

        # Pre-create an expired cache file
        import hashlib

        url_hash = hashlib.md5(url.encode()).hexdigest()
        cache_file = mock_auth_cache_dir / f"APIC_{url_hash}.json"
        cache_data = {
            "token": "expired-token",
            "expires_at": 500.0,  # Past time (current mock time is 1000.0)
        }
        with open(cache_file, "w") as f:
            json.dump(cache_data, f)

        # Act
        result = AuthCache._cache_auth_data(
            controller_type=controller_type,
            url=url,
            auth_func=sample_auth_func,
            extract_token=True,
        )

        # Assert
        assert result == "test-token-123"  # New token from auth_func
        sample_auth_func.assert_called_once()

        # Verify cache file was updated
        with open(cache_file, "r") as f:
            updated_data = json.load(f)
            assert updated_data["token"] == "test-token-123"
            assert updated_data["expires_at"] == 1000.0 + 3600 - 60

    def test_cache_expired_dict_mode(
        self,
        mock_auth_cache_dir: Path,
        mock_fcntl: Mock,
        mock_time: Mock,
        sample_dict_auth_func: Mock,
    ) -> None:
        """Test _cache_auth_data when cached data is expired (dict mode).

        This test verifies that when a cache file exists but is expired,
        the auth function is called to get new auth data and the cache
        is updated in extract_token=False mode.

        Args:
            mock_auth_cache_dir: Mocked auth cache directory path.
            mock_fcntl: Mocked file locking.
            mock_time: Mocked time.time() for consistent testing.
            sample_dict_auth_func: Mock authentication function returning dict.
        """
        # Arrange
        controller_type = "CC"
        url = "https://cc.example.com"

        # Pre-create an expired cache file (compute hash correctly)
        import hashlib

        url_hash = hashlib.md5(url.encode()).hexdigest()
        cache_file = mock_auth_cache_dir / f"CC_{url_hash}.json"
        cache_data = {
            "token": "expired-dict-token",
            "refresh_token": "expired-refresh",
            "expires_at": 500.0,  # Past time
        }
        with open(cache_file, "w") as f:
            json.dump(cache_data, f)

        # Act
        result = AuthCache._cache_auth_data(
            controller_type=controller_type,
            url=url,
            auth_func=sample_dict_auth_func,
            extract_token=False,
        )

        # Assert
        expected_result = {
            "token": "dict-token-456",
            "refresh_token": "refresh-789",
            "user_id": "user123",
        }
        assert result == expected_result
        sample_dict_auth_func.assert_called_once()

        # Verify cache file was updated
        with open(cache_file, "r") as f:
            updated_data = json.load(f)
            assert updated_data["token"] == "dict-token-456"
            assert updated_data["refresh_token"] == "refresh-789"
            assert updated_data["user_id"] == "user123"

    def test_cache_invalid_json(
        self,
        mock_auth_cache_dir: Path,
        mock_fcntl: Mock,
        mock_time: Mock,
        sample_auth_func: Mock,
    ) -> None:
        """Test _cache_auth_data when cache file contains invalid JSON.

        This test verifies that when a cache file exists but contains
        invalid JSON, the auth function is called and a new valid
        cache file is created.

        Args:
            mock_auth_cache_dir: Mocked auth cache directory path.
            mock_fcntl: Mocked file locking.
            mock_time: Mocked time.time() for consistent testing.
            sample_auth_func: Mock authentication function.
        """
        # Arrange
        controller_type = "APIC"
        url = "https://controller.example.com"

        # Pre-create a cache file with invalid JSON (compute hash correctly)
        import hashlib

        url_hash = hashlib.md5(url.encode()).hexdigest()
        cache_file = mock_auth_cache_dir / f"APIC_{url_hash}.json"
        with open(cache_file, "w") as f:
            f.write("{ invalid json content }")

        # Act
        result = AuthCache._cache_auth_data(
            controller_type=controller_type,
            url=url,
            auth_func=sample_auth_func,
            extract_token=True,
        )

        # Assert
        assert result == "test-token-123"
        sample_auth_func.assert_called_once()

        # Verify cache file was recreated with valid content
        with open(cache_file, "r") as f:
            cached_data = json.load(f)
            assert cached_data["token"] == "test-token-123"

    def test_cache_missing_key(
        self,
        mock_auth_cache_dir: Path,
        mock_fcntl: Mock,
        mock_time: Mock,
        sample_auth_func: Mock,
    ) -> None:
        """Test _cache_auth_data when cache file is missing required keys.

        This test verifies that when a cache file exists but is missing
        required keys (like expires_at), the auth function is called
        and a new valid cache file is created.

        Args:
            mock_auth_cache_dir: Mocked auth cache directory path.
            mock_fcntl: Mocked file locking.
            mock_time: Mocked time.time() for consistent testing.
            sample_auth_func: Mock authentication function.
        """
        # Arrange
        controller_type = "APIC"
        url = "https://controller.example.com"

        # Pre-create a cache file missing expires_at (compute hash correctly)
        import hashlib

        url_hash = hashlib.md5(url.encode()).hexdigest()
        cache_file = mock_auth_cache_dir / f"APIC_{url_hash}.json"
        cache_data = {"token": "incomplete-token"}  # Missing expires_at
        with open(cache_file, "w") as f:
            json.dump(cache_data, f)

        # Act
        result = AuthCache._cache_auth_data(
            controller_type=controller_type,
            url=url,
            auth_func=sample_auth_func,
            extract_token=True,
        )

        # Assert
        assert result == "test-token-123"
        sample_auth_func.assert_called_once()

    def test_file_locking_called(
        self,
        mock_auth_cache_dir: Path,
        mock_fcntl: Mock,
        mock_time: Mock,
        sample_auth_func: Mock,
    ) -> None:
        """Test that file locking is properly called during cache operations.

        This test verifies that fcntl.flock is called with the correct
        parameters to ensure thread/process safety during cache operations.

        Args:
            mock_auth_cache_dir: Mocked auth cache directory path.
            mock_fcntl: Mocked file locking.
            mock_time: Mocked time.time() for consistent testing.
            sample_auth_func: Mock authentication function.
        """
        # Arrange
        controller_type = "APIC"
        url = "https://controller.example.com"

        # Act
        AuthCache._cache_auth_data(
            controller_type=controller_type,
            url=url,
            auth_func=sample_auth_func,
            extract_token=True,
        )

        # Assert
        mock_fcntl.assert_called_once()
        # Verify it was called with LOCK_EX (exclusive lock)
        import fcntl

        call_args = mock_fcntl.call_args
        assert call_args[0][1] == fcntl.LOCK_EX

    def test_cache_file_permissions(
        self,
        mock_auth_cache_dir: Path,
        mock_fcntl: Mock,
        mock_time: Mock,
        sample_auth_func: Mock,
    ) -> None:
        """Test that cache files are created with secure permissions.

        This test verifies that cache files are created with 0o600
        permissions (read/write for owner only) for security.

        Args:
            mock_auth_cache_dir: Mocked auth cache directory path.
            mock_fcntl: Mocked file locking.
            mock_time: Mocked time.time() for consistent testing.
            sample_auth_func: Mock authentication function.
        """
        # Arrange
        controller_type = "APIC"
        url = "https://controller.example.com"

        # Act
        AuthCache._cache_auth_data(
            controller_type=controller_type,
            url=url,
            auth_func=sample_auth_func,
            extract_token=True,
        )

        # Assert
        cache_files = list(mock_auth_cache_dir.glob("*.json"))
        assert len(cache_files) == 1

        # Check file permissions (0o600 = 384 in decimal)
        file_stat = cache_files[0].stat()
        assert oct(file_stat.st_mode)[-3:] == "600"


class TestAuthCachePublicMethods:
    """Test cases for the public methods of AuthCache."""

    def test_get_or_create_calls_internal_correctly(
        self, mocker: "MockerFixture"
    ) -> None:
        """Test that get_or_create calls _cache_auth_data with correct parameters.

        This test verifies that the public get_or_create method properly
        delegates to _cache_auth_data with extract_token=False.

        Args:
            mocker: Pytest mocker fixture for creating mocks.
        """
        # Arrange
        mock_cache_auth_data = mocker.patch.object(
            AuthCache,
            "_cache_auth_data",
            return_value={"token": "test", "user": "admin"},
        )

        controller_type = "CC"
        url = "https://cc.example.com"
        auth_func = Mock(return_value=({"token": "test", "user": "admin"}, 3600))

        # Act
        result = AuthCache.get_or_create(
            controller_type=controller_type, url=url, auth_func=auth_func
        )

        # Assert
        assert result == {"token": "test", "user": "admin"}
        mock_cache_auth_data.assert_called_once_with(
            controller_type=controller_type,
            url=url,
            auth_func=auth_func,
            extract_token=False,
        )

    def test_get_or_create_token_calls_internal_correctly(
        self, mocker: "MockerFixture"
    ) -> None:
        """Test that get_or_create_token calls _cache_auth_data with correct parameters.

        This test verifies that the public get_or_create_token method
        properly delegates to _cache_auth_data with extract_token=True
        and wraps the auth function correctly.

        Args:
            mocker: Pytest mocker fixture for creating mocks.
        """
        # Arrange
        mock_cache_auth_data = mocker.patch.object(
            AuthCache, "_cache_auth_data", return_value="test-token-123"
        )

        controller_type = "APIC"
        url = "https://apic.example.com"
        username = "admin"
        password = "secret"
        auth_func = Mock(return_value=("test-token-123", 3600))

        # Act
        result = AuthCache.get_or_create_token(
            controller_type=controller_type,
            url=url,
            username=username,
            password=password,
            auth_func=auth_func,
        )

        # Assert
        assert result == "test-token-123"

        # Verify _cache_auth_data was called
        assert mock_cache_auth_data.called
        call_args = mock_cache_auth_data.call_args

        # Check basic parameters
        assert call_args.kwargs["controller_type"] == controller_type
        assert call_args.kwargs["url"] == url
        assert call_args.kwargs["extract_token"] is True

        # Test the wrapped auth function
        wrapped_func = call_args.kwargs["auth_func"]
        wrapped_result = wrapped_func()
        assert wrapped_result == ("test-token-123", 3600)
        auth_func.assert_called_once_with(url, username, password)

    def test_get_or_create_token_backward_compatibility(
        self, mock_auth_cache_dir: Path, mock_fcntl: Mock, mock_time: Mock
    ) -> None:
        """Test backward compatibility of get_or_create_token.

        This test verifies that get_or_create_token maintains backward
        compatibility with the original token-based caching behavior.

        Args:
            mock_auth_cache_dir: Mocked auth cache directory path.
            mock_fcntl: Mocked file locking.
            mock_time: Mocked time.time() for consistent testing.
        """

        # Arrange
        def mock_auth_func(url: str, username: str, password: str) -> Tuple[str, int]:
            """Mock authentication function for testing."""
            assert url == "https://apic.example.com"
            assert username == "admin"
            assert password == "password123"
            return "backward-compat-token", 3600

        # Act
        result = AuthCache.get_or_create_token(
            controller_type="APIC",
            url="https://apic.example.com",
            username="admin",
            password="password123",
            auth_func=mock_auth_func,
        )

        # Assert
        assert result == "backward-compat-token"

        # Verify cache file was created
        cache_files = list(mock_auth_cache_dir.glob("*.json"))
        assert len(cache_files) == 1

        with open(cache_files[0], "r") as f:
            cached_data = json.load(f)
            assert cached_data["token"] == "backward-compat-token"


class TestAuthCacheIntegration:
    """Integration tests for AuthCache with multiple scenarios."""

    def test_concurrent_access_simulation(
        self, mock_auth_cache_dir: Path, mock_fcntl: Mock, mock_time: Mock
    ) -> None:
        """Test that multiple calls with same parameters reuse cache.

        This test simulates concurrent access by making multiple calls
        with the same parameters and verifying that the auth function
        is only called once due to caching.

        Args:
            mock_auth_cache_dir: Mocked auth cache directory path.
            mock_fcntl: Mocked file locking.
            mock_time: Mocked time.time() for consistent testing.
        """
        # Arrange
        auth_call_count = 0

        def counting_auth_func() -> Tuple[Dict[str, Any], int]:
            """Auth function that counts how many times it's called."""
            nonlocal auth_call_count
            auth_call_count += 1
            return {"token": f"token-{auth_call_count}", "count": auth_call_count}, 3600

        # Act - Make multiple calls
        result1 = AuthCache.get_or_create(
            controller_type="CC",
            url="https://cc.example.com",
            auth_func=counting_auth_func,
        )

        result2 = AuthCache.get_or_create(
            controller_type="CC",
            url="https://cc.example.com",
            auth_func=counting_auth_func,
        )

        result3 = AuthCache.get_or_create(
            controller_type="CC",
            url="https://cc.example.com",
            auth_func=counting_auth_func,
        )

        # Assert
        assert auth_call_count == 1  # Auth function called only once
        assert result1 == result2 == result3
        assert result1 == {"token": "token-1", "count": 1}

    def test_different_urls_create_different_caches(
        self, mock_auth_cache_dir: Path, mock_fcntl: Mock, mock_time: Mock
    ) -> None:
        """Test that different URLs create separate cache entries.

        This test verifies that cache entries are properly isolated
        by URL, ensuring different controllers don't share caches.

        Args:
            mock_auth_cache_dir: Mocked auth cache directory path.
            mock_fcntl: Mocked file locking.
            mock_time: Mocked time.time() for consistent testing.
        """

        # Arrange
        def auth_func_1() -> Tuple[Dict[str, Any], int]:
            return {"token": "controller1-token"}, 3600

        def auth_func_2() -> Tuple[Dict[str, Any], int]:
            return {"token": "controller2-token"}, 3600

        # Act
        result1 = AuthCache.get_or_create(
            controller_type="CC",
            url="https://controller1.example.com",
            auth_func=auth_func_1,
        )

        result2 = AuthCache.get_or_create(
            controller_type="CC",
            url="https://controller2.example.com",
            auth_func=auth_func_2,
        )

        # Assert
        assert result1 == {"token": "controller1-token"}
        assert result2 == {"token": "controller2-token"}

        # Verify two separate cache files were created
        cache_files = list(mock_auth_cache_dir.glob("*.json"))
        assert len(cache_files) == 2

    def test_different_controller_types_create_different_caches(
        self, mock_auth_cache_dir: Path, mock_fcntl: Mock, mock_time: Mock
    ) -> None:
        """Test that different controller types create separate cache entries.

        This test verifies that cache entries are properly isolated
        by controller type, even for the same URL.

        Args:
            mock_auth_cache_dir: Mocked auth cache directory path.
            mock_fcntl: Mocked file locking.
            mock_time: Mocked time.time() for consistent testing.
        """

        # Arrange
        def auth_func_apic() -> Tuple[Dict[str, Any], int]:
            return {"token": "apic-token"}, 3600

        def auth_func_cc() -> Tuple[Dict[str, Any], int]:
            return {"token": "cc-token"}, 3600

        # Act
        result1 = AuthCache.get_or_create(
            controller_type="APIC",
            url="https://controller.example.com",
            auth_func=auth_func_apic,
        )

        result2 = AuthCache.get_or_create(
            controller_type="CC",
            url="https://controller.example.com",
            auth_func=auth_func_cc,
        )

        # Assert
        assert result1 == {"token": "apic-token"}
        assert result2 == {"token": "cc-token"}

        # Verify two separate cache files were created
        cache_files = list(mock_auth_cache_dir.glob("*.json"))
        assert len(cache_files) == 2

    @pytest.mark.parametrize(
        "initial_time,check_time,should_refresh",
        [
            (1000.0, 1500.0, False),  # 500s passed, cache still valid (expires at 4540)
            (1000.0, 4539.9, False),  # Just before expiry boundary, still valid
            (
                1000.0,
                4540.0,
                True,
            ),  # Exactly at expiry boundary, cache expired (< is strict)
            (1000.0, 5000.0, True),  # Well past expiry, should refresh
        ],
    )
    def test_ttl_behavior(
        self,
        mock_auth_cache_dir: Path,
        mock_fcntl: Mock,
        mocker: "MockerFixture",
        initial_time: float,
        check_time: float,
        should_refresh: bool,
    ) -> None:
        """Test TTL behavior with different time scenarios.

        This parametrized test verifies that cache expiry is correctly
        handled at different points in time relative to the TTL.

        Args:
            mock_auth_cache_dir: Mocked auth cache directory path.
            mock_fcntl: Mocked file locking.
            mocker: Pytest mocker fixture for creating mocks.
            initial_time: Initial time when cache is created.
            check_time: Time when cache is checked.
            should_refresh: Whether the cache should be refreshed.
        """
        # Arrange
        time_mock = mocker.patch("nac_test.pyats_core.common.auth_cache.time.time")
        time_mock.return_value = initial_time

        auth_call_count = 0

        def counting_auth_func() -> Tuple[Dict[str, Any], int]:
            """Auth function that counts calls."""
            nonlocal auth_call_count
            auth_call_count += 1
            return {"token": f"token-v{auth_call_count}"}, 3600

        # Create initial cache
        result1 = AuthCache.get_or_create(
            controller_type="CC",
            url="https://cc.example.com",
            auth_func=counting_auth_func,
        )
        assert result1 == {"token": "token-v1"}
        assert auth_call_count == 1

        # Act - Check cache at different time
        time_mock.return_value = check_time
        result2 = AuthCache.get_or_create(
            controller_type="CC",
            url="https://cc.example.com",
            auth_func=counting_auth_func,
        )

        # Assert
        if should_refresh:
            assert auth_call_count == 2
            assert result2 == {"token": "token-v2"}
        else:
            assert auth_call_count == 1
            assert result2 == {"token": "token-v1"}


class TestAuthCacheErrorHandling:
    """Test error handling scenarios in AuthCache."""

    def test_auth_func_exception_propagated(
        self, mock_auth_cache_dir: Path, mock_fcntl: Mock, mock_time: Mock
    ) -> None:
        """Test that exceptions from auth_func are properly propagated.

        This test verifies that when the authentication function raises
        an exception, it is properly propagated to the caller.

        Args:
            mock_auth_cache_dir: Mocked auth cache directory path.
            mock_fcntl: Mocked file locking.
            mock_time: Mocked time.time() for consistent testing.
        """

        # Arrange
        def failing_auth_func() -> Tuple[Dict[str, Any], int]:
            raise ValueError("Authentication failed")

        # Act & Assert
        with pytest.raises(ValueError, match="Authentication failed"):
            AuthCache.get_or_create(
                controller_type="CC",
                url="https://cc.example.com",
                auth_func=failing_auth_func,
            )

    def test_cache_dir_creation(
        self, mocker: "MockerFixture", tmp_path: Path, mock_fcntl: Mock, mock_time: Mock
    ) -> None:
        """Test that cache directory is created if it doesn't exist.

        This test verifies that the AUTH_CACHE_DIR is created
        automatically if it doesn't exist.

        Args:
            mocker: Pytest mocker fixture for creating mocks.
            tmp_path: Pytest fixture providing a temporary directory.
            mock_fcntl: Mocked file locking.
            mock_time: Mocked time.time() for consistent testing.
        """
        # Arrange
        non_existent_dir = tmp_path / "new-cache-dir"
        mocker.patch(
            "nac_test.pyats_core.common.auth_cache.AUTH_CACHE_DIR",
            str(non_existent_dir),
        )

        assert not non_existent_dir.exists()

        auth_func = Mock(return_value=({"token": "test"}, 3600))

        # Act
        AuthCache.get_or_create(
            controller_type="CC", url="https://cc.example.com", auth_func=auth_func
        )

        # Assert
        assert non_existent_dir.exists()
        assert non_existent_dir.is_dir()
