# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt

"""Pytest fixtures for integration tests."""

import os
import re
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from tests.integration.mocks.mock_server import MockAPIServer

# Path to the default YAML configuration file
DEFAULT_CONFIG_PATH = Path(__file__).parent / "fixtures" / "mock_api_config.yaml"


@pytest.fixture(scope="class")
def class_mocker() -> Generator[pytest.MonkeyPatch, None, None]:
    """Provide a class-scoped monkeypatch fixture for environment variable management.

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


@pytest.fixture(scope="session", autouse=True)
def clear_controller_credentials() -> None:
    """
    Clear any controller credentials from environment to avoid conflicts.

    nac-test fails if the user has already a controller credential
    set in his/her environment.
    This fixture removes any environment variables matching the pattern:
    ^[A-Z]+_(URL|USERNAME|PASSWORD)$

    Runs at session scope to ensure credentials are cleared before any
    class-scoped or function-scoped fixtures that might set their own
    mock credentials.
    """
    pattern = re.compile(r"^[A-Z]+_(URL|USERNAME|PASSWORD)$")
    keys_to_remove = [key for key in os.environ.keys() if pattern.match(key)]
    for key in keys_to_remove:
        del os.environ[key]


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


@pytest.fixture(scope="session")
def sdwan_user_testbed() -> Generator[str, None, None]:
    """Create a user testbed YAML with mock device connections for SDWAN tests.

    This fixture creates a temporary testbed file that can be shared across
    multiple test modules for SDWAN integration tests.

    Returns:
        Path string to the testbed YAML file
    """
    # Get absolute path to mock_unicon.py
    project_root = Path(__file__).parent.parent.parent.absolute()
    mock_script = project_root / "tests" / "integration" / "mocks" / "mock_unicon.py"

    # Create testbed YAML with mock device connections
    # Devices sd-dc-c8kv-01 and sd-dc-c8kv-02 are from the SDWAN fixture data
    testbed_content = f"""
testbed:
  name: integration_test_testbed
  credentials:
    default:
      username: admin
      password: admin

devices:
  sd-dc-c8kv-01:
    os: iosxe
    type: router
    connections:
      cli:
        command: python {mock_script} iosxe --hostname sd-dc-c8kv-01

  sd-dc-c8kv-02:
    os: iosxe
    type: router
    connections:
      cli:
        command: python {mock_script} iosxe --hostname sd-dc-c8kv-02
"""

    # Create temporary file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix="_testbed.yaml", delete=False
    ) as f:
        f.write(testbed_content)
        testbed_path = Path(f.name)

    try:
        yield str(testbed_path)
    finally:
        # Cleanup
        if testbed_path.exists():
            testbed_path.unlink()
