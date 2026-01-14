# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Generic file-based authentication token caching for parallel processes."""

import fcntl
import hashlib
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from nac_test.pyats_core.constants import AUTH_CACHE_DIR


class AuthCache:
    """Generic file-based auth token caching across parallel processes

    This is controller-agnostic - each architecture provides their own auth function
    """

    @classmethod
    def _cache_auth_data(
        cls,
        controller_type: str,
        url: str,
        auth_func: Callable[[], tuple[Any, int]],
        extract_token: bool = False,
    ) -> Any:
        """Internal method for caching auth data with file-based locking.

        Args:
            controller_type: Type of controller
            url: Controller URL
            auth_func: Function that returns (auth_data, expires_in_seconds)
            extract_token: If True, expects auth_data to be a string token.
                          If False, expects a dict.

        Returns:
            Either a token string or auth dict based on extract_token flag
        """
        cache_dir = Path(AUTH_CACHE_DIR)
        cache_dir.mkdir(exist_ok=True)

        url_hash = hashlib.md5(url.encode(), usedforsecurity=False).hexdigest()
        cache_file = cache_dir / f"{controller_type}_{url_hash}.json"
        lock_file = cache_dir / f"{controller_type}_{url_hash}.lock"

        with open(lock_file, "w") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)

            # Check if valid cached data exists
            if cache_file.exists():
                try:
                    with open(cache_file) as f:
                        data = json.load(f)
                        if time.time() < data["expires_at"]:
                            # Return based on what type of data we're working with
                            if extract_token:
                                return str(data["token"])
                            else:
                                # Return the auth_data dict (minus expires_at)
                                auth_data = {
                                    k: v for k, v in data.items() if k != "expires_at"
                                }
                                return auth_data
                except (json.JSONDecodeError, KeyError, TypeError):
                    pass  # Invalid file, will recreate

            # Get new auth data
            auth_data, expires_in = auth_func()

            # Prepare cache data
            cache_data: dict[str, Any] = {"expires_at": time.time() + expires_in - 60}

            if extract_token:
                # Legacy token mode - auth_data is a string
                cache_data["token"] = str(auth_data)
                result: Any = str(auth_data)
            else:
                # Generic dict mode - merge auth_data dict
                auth_dict = (
                    dict(auth_data) if not isinstance(auth_data, dict) else auth_data
                )
                cache_data.update(auth_dict)
                result = auth_dict

            # Cache it
            with open(cache_file, "w") as f:
                json.dump(cache_data, f)

            cache_file.chmod(0o600)
            return result

    @classmethod
    def get_or_create(
        cls,
        controller_type: str,
        url: str,
        auth_func: Callable[[], tuple[dict[str, Any], int]],
    ) -> dict[str, Any]:
        """Get existing auth data dict or create new one with file-based locking.

        Generic method for caching any JSON-serializable dict.

        Args:
            controller_type: Type of controller (SDWAN_MANAGER, CC, etc)
            url: Controller URL
            auth_func: Function that returns (auth_dict, expires_in_seconds)

        Returns:
            Dict containing authentication data (without expires_at)
        """
        result = cls._cache_auth_data(
            controller_type=controller_type,
            url=url,
            auth_func=auth_func,
            extract_token=False,
        )
        # Type narrowing for mypy - we know it's a dict when extract_token=False
        assert isinstance(result, dict)
        return result

    @classmethod
    def get_or_create_token(
        cls,
        controller_type: str,
        url: str,
        username: str,
        password: str,
        auth_func: Callable[[str, str, str], tuple[str, int]],
    ) -> str:
        """Get existing token or create new one with file-based locking

        Args:
            controller_type: Type of controller (APIC, CC, etc)
            url: Controller URL
            username: Username for authentication
            password: Password for authentication
            auth_func: Architecture-specific auth function that returns (token, expires_in_seconds)
        """

        # Create a wrapper function that captures the username/password
        def wrapped_auth_func() -> tuple[str, int]:
            return auth_func(url, username, password)

        result = cls._cache_auth_data(
            controller_type=controller_type,
            url=url,
            auth_func=wrapped_auth_func,
            extract_token=True,
        )
        # Type narrowing for mypy - we know it's a str when extract_token=True
        assert isinstance(result, str)
        return result
