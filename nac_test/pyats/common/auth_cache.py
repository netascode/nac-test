# -*- coding: utf-8 -*-

"""Generic file-based authentication token caching for parallel processes."""

import fcntl
import json
import time
import hashlib
from pathlib import Path
from typing import Callable, Tuple

from nac_test.pyats.constants import AUTH_CACHE_DIR


class AuthCache:
    """Generic file-based auth token caching across parallel processes

    This is controller-agnostic - each architecture provides their own auth function
    """

    @classmethod
    def get_or_create_token(
        cls,
        controller_type: str,
        url: str,
        username: str,
        password: str,
        auth_func: Callable[[str, str, str], Tuple[str, int]],
    ) -> str:
        """Get existing token or create new one with file-based locking

        Args:
            controller_type: Type of controller (APIC, DNAC, etc)
            url: Controller URL
            username: Username for authentication
            password: Password for authentication
            auth_func: Architecture-specific auth function that returns (token, expires_in_seconds)
        """
        cache_dir = Path(AUTH_CACHE_DIR)
        cache_dir.mkdir(exist_ok=True)

        # Create unique filename based on controller URL
        url_hash = hashlib.md5(url.encode()).hexdigest()
        token_file = cache_dir / f"{controller_type}_{url_hash}.json"
        lock_file = cache_dir / f"{controller_type}_{url_hash}.lock"

        # Use file locking to ensure only one process authenticates
        with open(lock_file, "w") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)

            # Check if valid token exists
            if token_file.exists():
                try:
                    with open(token_file, "r") as f:
                        data = json.load(f)
                        if time.time() < data["expires_at"]:
                            return str(data["token"])
                except (json.JSONDecodeError, KeyError, TypeError):
                    pass  # Invalid file, will recreate

            # Get new token using architecture-specific function
            token, expires_in = auth_func(url, username, password)

            # Cache it with expiration
            with open(token_file, "w") as f:
                json.dump(
                    {
                        "token": token,
                        "expires_at": time.time() + expires_in - 60,  # 1 min buffer
                    },
                    f,
                )

            return token
