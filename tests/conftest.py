# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Global pytest fixtures shared across all test modules.

This module provides common fixtures used by both integration and E2E tests:
- Environment cleanup (controller credentials, proxy settings)
- Mock API server for simulating controller responses
- Class-scoped monkeypatch for environment variable management
"""

import os
import re
from collections.abc import Generator
from pathlib import Path

import pytest

from tests.e2e.mocks.mock_server import MockAPIServer

# Path to the mock API configuration file
MOCK_API_CONFIG_PATH = Path(__file__).parent / "e2e" / "mocks" / "mock_api_config.yaml"


# =============================================================================
# Session-scoped fixtures (shared across all tests)
# =============================================================================


@pytest.fixture(scope="session", autouse=True)
def clear_controller_credentials() -> None:
    """Clear any controller credentials from environment to avoid conflicts.

    nac-test fails if the user has controller credentials set in their
    environment. This fixture removes any environment variables matching
    the pattern: ^[A-Z]+_(URL|USERNAME|PASSWORD)$

    Runs at session scope to ensure credentials are cleared before any
    other fixtures that might set mock credentials.
    """
    pattern = re.compile(r"^[A-Z]+_(URL|USERNAME|PASSWORD)$")
    keys_to_remove = [key for key in os.environ.keys() if pattern.match(key)]
    for key in keys_to_remove:
        del os.environ[key]


@pytest.fixture(scope="session", autouse=True)
def bypass_proxy_for_localhost() -> Generator[None, None, None]:
    """Ensure 127.0.0.1 is in no_proxy to bypass corporate proxy.

    The mock API server runs on 127.0.0.1 and must not route through proxies.
    This fixture ensures proxy bypass is configured for the entire test session.
    """
    original_no_proxy = os.environ.get("no_proxy", "")
    original_NO_PROXY = os.environ.get("NO_PROXY", "")

    if "127.0.0.1" not in original_no_proxy:
        new_no_proxy = (
            f"{original_no_proxy},127.0.0.1" if original_no_proxy else "127.0.0.1"
        )
        os.environ["no_proxy"] = new_no_proxy

    if "127.0.0.1" not in original_NO_PROXY:
        new_NO_PROXY = (
            f"{original_NO_PROXY},127.0.0.1" if original_NO_PROXY else "127.0.0.1"
        )
        os.environ["NO_PROXY"] = new_NO_PROXY

    yield

    if original_no_proxy:
        os.environ["no_proxy"] = original_no_proxy
    elif "no_proxy" in os.environ:
        del os.environ["no_proxy"]

    if original_NO_PROXY:
        os.environ["NO_PROXY"] = original_NO_PROXY
    elif "NO_PROXY" in os.environ:
        del os.environ["NO_PROXY"]


@pytest.fixture(scope="session")
def mock_api_server() -> Generator[MockAPIServer, None, None]:
    """Provide a mock API server for integration and E2E tests.

    The server starts automatically once per test session and loads
    configuration from tests/e2e/mocks/mock_api_config.yaml.

    You can override the config file by setting the MOCK_API_CONFIG
    environment variable.

    The server is accessible at http://127.0.0.1:5555 by default.

    Example usage in tests:
        def test_api_call(mock_api_server):
            response = requests.get(f"{mock_api_server.url}/api/devices")
            assert response.status_code == 200

            # You can also add endpoints dynamically
            mock_api_server.add_endpoint(
                name='Custom',
                path_pattern='/api/custom',
                status_code=200,
                response_data={'custom': 'data'},
                match_type='exact'
            )
    """
    server = MockAPIServer()

    config_path = os.environ.get("MOCK_API_CONFIG", str(MOCK_API_CONFIG_PATH))
    config_file = Path(config_path)

    if config_file.exists():
        server.load_from_yaml(config_file)

    server.start()
    yield server
    server.reset_endpoints()
    server.stop()


# =============================================================================
# Class-scoped fixtures
# =============================================================================


@pytest.fixture(scope="class")
def class_mocker() -> Generator[pytest.MonkeyPatch, None, None]:
    """Provide a class-scoped monkeypatch fixture for environment management.

    This allows class-scoped fixtures to use monkeypatch for automatic cleanup
    of environment variables instead of manual save/restore logic.

    Usage in class-scoped fixtures:
        @pytest.fixture(scope="class")
        def my_fixture(class_mocker: pytest.MonkeyPatch):
            class_mocker.setenv("MY_VAR", "value")
            # Automatic cleanup when class scope ends
    """
    monkey_patch = pytest.MonkeyPatch()
    yield monkey_patch
    monkey_patch.undo()
