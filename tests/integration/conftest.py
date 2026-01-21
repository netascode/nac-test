# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Pytest fixtures for integration tests."""

import os
from collections.abc import Generator
from pathlib import Path

import pytest

from tests.integration.mocks.mock_server import MockAPIServer


@pytest.fixture(scope="session", autouse=True)
def bypass_proxy_for_localhost() -> Generator[None, None, None]:
    """Ensure 127.0.0.1 is in no_proxy to bypass corporate proxy for mock server.

    The mock API server runs on 127.0.0.1 and must not route through proxies.
    This fixture ensures proxy bypass is configured for the entire test session.
    """
    # Store original values
    original_no_proxy = os.environ.get("no_proxy", "")
    original_NO_PROXY = os.environ.get("NO_PROXY", "")

    # Add 127.0.0.1 if not already present
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

    # Restore original values
    if original_no_proxy:
        os.environ["no_proxy"] = original_no_proxy
    elif "no_proxy" in os.environ:
        del os.environ["no_proxy"]

    if original_NO_PROXY:
        os.environ["NO_PROXY"] = original_NO_PROXY
    elif "NO_PROXY" in os.environ:
        del os.environ["NO_PROXY"]


# Path to the default YAML configuration file
DEFAULT_CONFIG_PATH = Path(__file__).parent / "fixtures" / "mock_api_config.yaml"

# To see mock server logs, set logging level to INFO or DEBUG in your tests:
#
# INFO level shows:
#   - Server startup/shutdown
#   - Incoming requests and matched endpoints
#   - Response status codes
#
# DEBUG level additionally shows:
#   - Request headers and body
#   - Full response data (JSON)
#   - All pattern matching attempts
#
# Enable with:
#   logging.basicConfig(level=logging.INFO)
# or for more detail:
#   logging.basicConfig(level=logging.DEBUG)
# or target just the mock server:
#   logging.getLogger('tests.integration.mock_server').setLevel(logging.DEBUG)


@pytest.fixture(scope="session")
def mock_api_server() -> Generator[MockAPIServer, None, None]:
    """Provide a mock API server that auto-starts for all integration tests.

    The server starts automatically once per test session and loads configuration
    from the YAML file at tests/integration/fixtures/mock_api_config.yaml.

    You can override the config file by setting the MOCK_API_CONFIG environment variable.

    The server is accessible at http://127.0.0.1:5555 by default.

    Example usage in tests:
        def test_api_call(mock_api_server):
            import requests
            # Server is already running with YAML config loaded
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

    # Load configuration from YAML file
    config_path = os.environ.get("MOCK_API_CONFIG", str(DEFAULT_CONFIG_PATH))
    config_file = Path(config_path)

    if config_file.exists():
        server.load_from_yaml(config_file)
    else:
        # If no config file exists, just start the server without pre-configured endpoints
        pass

    server.start()
    yield server
    server.reset_endpoints()
    server.stop()


@pytest.fixture(scope="function")
def mock_api_server_isolated(
    mock_api_server: MockAPIServer,
) -> Generator[MockAPIServer, None, None]:
    """Provide a mock API server with per-test isolation.

    This fixture wraps the session-scoped mock_api_server and automatically
    resets dynamically added endpoints after each test. Use this fixture
    instead of mock_api_server when your test adds endpoints dynamically
    and you want to ensure those endpoints don't leak into other tests.

    Example usage in tests:
        def test_custom_endpoint(mock_api_server_isolated):
            # Add a test-specific endpoint
            mock_api_server_isolated.add_endpoint(
                name='Test Endpoint',
                path_pattern='/api/test',
                status_code=201,
                response_data={'created': True},
                match_type='exact'
            )
            # Test logic here...
            # Endpoint is automatically removed after this test completes
    """
    yield mock_api_server
    mock_api_server.reset_endpoints()
